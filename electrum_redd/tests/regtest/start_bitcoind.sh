#!/usr/bin/env bash
export HOME=~
set -eux pipefail
mkdir -p ~/.reddcoin
cat > ~/.reddcoin/reddcoin.conf <<EOF
regtest=1
txindex=1
printtoconsole=1
rpcuser=doggman
rpcpassword=donkey
rpcallowip=127.0.0.1
zmqpubrawblock=tcp://127.0.0.1:28332
zmqpubrawtx=tcp://127.0.0.1:28333
fallbackfee=0.0002
[regtest]
rpcbind=0.0.0.0
rpcport=18554
EOF
rm -rf ~/.reddcoin/regtest
screen -S reddcoind -X quit || true
screen -S reddcoind -m -d reddcoind -regtest
sleep 6
addr=$(reddcoin-cli getnewaddress)
reddcoin-cli generatetoaddress 150 $addr > /dev/null
