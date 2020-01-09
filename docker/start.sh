#!/bin/bash

/app/lumino/geth account new --password /app/lumino/passwd
ls /root/.ethereum/keystore
export KEYSTORE_PATH=/root/.ethereum/keystore
export RSK_NODE_URL=http://142.93.207.229:4444
export TOKENNETWORK_REGISTRY_CONTRACT_ADDRESS=0x7385f5c9Fb5D5cd11b689264756A847359d2FDc7
export SECRET_REGISTRY_CONTRACT_ADDRESS=0x59e1344572EC42BB0BB95046E07d6509Bc737b57
export ENDPOINT_REGISTRY_CONTRACT_ADDRESS=0x6BEb99b6eCac8E4E2EdeC141042135D0dD8F15c1
export YOUR_RNS_DOMAIN=
export PASS=12345
/app/lumino/run.exp
