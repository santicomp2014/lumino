import structlog
import json

from raiden.constants import EMPTY_SECRET, TEST_PAYMENT_ID
from raiden.lightclient.light_client_message_handler import LightClientMessageHandler
from raiden.messages import (
    Delivered,
    LockedTransfer,
    LockExpired,
    Message,
    Processed,
    RefundTransfer,
    RevealSecret,
    SecretRequest,
    Unlock,
)
from raiden.raiden_service import RaidenService
from raiden.routing import get_best_routes
from raiden.storage.wal import WriteAheadLog
from raiden.transfer import views
from raiden.transfer.architecture import StateChange
from raiden.transfer.mediated_transfer.state import lockedtransfersigned_from_message
from raiden.transfer.mediated_transfer.state_change import (
    ReceiveLockExpired,
    ReceiveSecretRequest,
    ReceiveSecretReveal,
    ReceiveTransferRefund,
    ReceiveTransferRefundCancelRoute,
    ReceiveSecretRequestLight, ReceiveSecretRevealLight)
from raiden.transfer.state import balanceproof_from_envelope
from raiden.transfer.state_change import ReceiveDelivered, ReceiveProcessed, ReceiveUnlock
from raiden.utils import pex, random_secret
from raiden.utils.typing import MYPY_ANNOTATION, InitiatorAddress, PaymentAmount, TokenNetworkID, Union

log = structlog.get_logger(__name__)  # pylint: disable=invalid-name


class MessageHandler:
    def on_message(self, raiden: RaidenService, message: Message, is_light_client: bool = False) -> None:
        # pylint: disable=unidiomatic-typecheck
        print("On received message " + str(type(message)))

        if type(message) == SecretRequest:
            assert isinstance(message, SecretRequest), MYPY_ANNOTATION
            self.handle_message_secretrequest(raiden, message, is_light_client)

        elif type(message) == RevealSecret:
            assert isinstance(message, RevealSecret), MYPY_ANNOTATION
            self.handle_message_revealsecret(raiden, message, is_light_client)

        elif type(message) == Unlock:
            assert isinstance(message, Unlock), MYPY_ANNOTATION
            self.handle_message_unlock(raiden, message)

        elif type(message) == LockExpired:
            assert isinstance(message, LockExpired), MYPY_ANNOTATION
            self.handle_message_lockexpired(raiden, message)

        elif type(message) == RefundTransfer:
            assert isinstance(message, RefundTransfer), MYPY_ANNOTATION
            self.handle_message_refundtransfer(raiden, message)

        elif type(message) == LockedTransfer:
            assert isinstance(message, LockedTransfer), MYPY_ANNOTATION
            self.handle_message_lockedtransfer(raiden, message)

        elif type(message) == Delivered:
            assert isinstance(message, Delivered), MYPY_ANNOTATION
            self.handle_message_delivered(raiden, message, is_light_client)

        elif type(message) == Processed:
            assert isinstance(message, Processed), MYPY_ANNOTATION
            self.handle_message_processed(raiden, message, is_light_client)
        else:
            log.error("Unknown message cmdid {}".format(message.cmdid))

    @staticmethod
    def handle_message_secretrequest(raiden: RaidenService, message: SecretRequest,
                                     is_light_client: bool = False) -> None:

        if is_light_client:
            secret_request_light = ReceiveSecretRequestLight(
                message.payment_identifier,
                message.amount,
                message.expiration,
                message.secrethash,
                message.sender,
                message
            )
            raiden.handle_and_track_state_change(secret_request_light)
        else:
            secret_request = ReceiveSecretRequest(
                message.payment_identifier,
                message.amount,
                message.expiration,
                message.secrethash,
                message.sender,
            )
            raiden.handle_and_track_state_change(secret_request)

    @staticmethod
    def handle_message_revealsecret(raiden: RaidenService, message: RevealSecret, is_light_client=False) -> None:
        if is_light_client:
            state_change = ReceiveSecretRevealLight(message.secret, message.sender, message)
            raiden.handle_and_track_state_change(state_change)
        else:
            state_change = ReceiveSecretReveal(message.secret, message.sender)
            raiden.handle_and_track_state_change(state_change)

    @staticmethod
    def handle_message_unlock(raiden: RaidenService, message: Unlock) -> None:
        balance_proof = balanceproof_from_envelope(message)
        state_change = ReceiveUnlock(
            message_identifier=message.message_identifier,
            secret=message.secret,
            balance_proof=balance_proof,
        )
        raiden.handle_and_track_state_change(state_change)

    @staticmethod
    def handle_message_lockexpired(raiden: RaidenService, message: LockExpired) -> None:
        balance_proof = balanceproof_from_envelope(message)
        state_change = ReceiveLockExpired(
            balance_proof=balance_proof,
            secrethash=message.secrethash,
            message_identifier=message.message_identifier,
        )
        raiden.handle_and_track_state_change(state_change)

    @staticmethod
    def handle_message_refundtransfer(raiden: RaidenService, message: RefundTransfer) -> None:
        token_network_address = message.token_network_address
        from_transfer = lockedtransfersigned_from_message(message)
        chain_state = views.state_from_raiden(raiden)

        # FIXME: Shouldn't request routes here
        routes, _ = get_best_routes(
            chain_state=chain_state,
            token_network_id=TokenNetworkID(token_network_address),
            one_to_n_address=raiden.default_one_to_n_address,
            from_address=InitiatorAddress(raiden.address),
            to_address=from_transfer.target,
            amount=PaymentAmount(from_transfer.lock.amount),  # FIXME: mypy; deprecated by #3863
            previous_address=message.sender,
            config=raiden.config,
            privkey=raiden.privkey,
        )

        role = views.get_transfer_role(
            chain_state=chain_state, secrethash=from_transfer.lock.secrethash
        )

        state_change: StateChange
        if role == "initiator":
            old_secret = views.get_transfer_secret(chain_state, from_transfer.lock.secrethash)
            # We currently don't allow multi routes if the initiator does not
            # hold the secret. In such case we remove all other possible routes
            # which allow the API call to return with with an error message.
            if old_secret == EMPTY_SECRET:
                routes = list()

            secret = random_secret()
            state_change = ReceiveTransferRefundCancelRoute(
                routes=routes, transfer=from_transfer, secret=secret
            )
        else:
            state_change = ReceiveTransferRefund(transfer=from_transfer, routes=routes)

        raiden.handle_and_track_state_change(state_change)

    @staticmethod
    def handle_message_lockedtransfer(raiden: RaidenService, message: LockedTransfer) -> None:
        secrethash = message.lock.secrethash
        # We must check if the secret was registered against the latest block,
        # even if the block is forked away and the transaction that registers
        # the secret is removed from the blockchain. The rationale here is that
        # someone else does know the secret, regardless of the chain state, so
        # the node must not use it to start a payment.
        #
        # For this particular case, it's preferable to use `latest` instead of
        # having a specific block_hash, because it's preferable to know if the secret
        # was ever known, rather than having a consistent view of the blockchain.
        registered = raiden.default_secret_registry.is_secret_registered(
            secrethash=secrethash, block_identifier="latest"
        )
        if registered:
            log.warning(
                f"Ignoring received locked transfer with secrethash {pex(secrethash)} "
                f"since it is already registered in the secret registry"
            )
            return

        # TODO marcosmartinez7: what about lc reception here?
        if message.target == raiden.address:
            raiden.target_mediated_transfer(message)
        else:
            raiden.mediate_mediated_transfer(message)

    @classmethod
    def handle_message_processed(cls, raiden: RaidenService, message: Processed, is_light_client: bool = False) -> None:
        processed = ReceiveProcessed(message.sender, message.message_identifier)
        raiden.handle_and_track_state_change(processed)
        if is_light_client:
            cls.store_ack_message(message, raiden.wal)

    @classmethod
    def handle_message_delivered(cls, raiden: RaidenService, message: Delivered, is_light_client: bool = False) -> None:
        delivered = ReceiveDelivered(message.sender, message.delivered_message_identifier)
        raiden.handle_and_track_state_change(delivered)
        if is_light_client:
            cls.store_ack_message(message, raiden.wal)

    @staticmethod
    def store_ack_message(message: Union[Processed, Delivered], wal: WriteAheadLog):
        # If exists for that payment, the same message by the order, then discard it.
        is_delivered = type(message) == Delivered
        message_identifier = None
        if is_delivered:
            message_identifier = message.delivered_message_identifier
        else:
            message_identifier = message.message_identifier

        protocol_message = LightClientMessageHandler.get_light_client_protocol_message_by_identifier(
            message_identifier, wal)
        json_message = None
        if protocol_message.signed_message is None:
            json_message = protocol_message.unsigned_message
        else:
            json_message = protocol_message.signed_message

        json_message = json.loads(json_message)
        order = LightClientMessageHandler.get_order_for_ack(json_message["type"], message.__class__.__name__.lower())
        if order == -1:
            log.error("Unable to find principal message for {} {}: ".format(message.__class__.__name__,
                                                                            message_identifier))
        else:
            exists = LightClientMessageHandler.is_light_client_protocol_message_already_stored_message_id(
                message_identifier, protocol_message.light_client_payment_id, order, wal)
            if not exists:
                LightClientMessageHandler.store_light_client_protocol_message(
                    message_identifier, message, True, protocol_message.light_client_payment_id, order,
                    wal)
            else:
                log.info("Message for lc already received, ignoring db storage")
