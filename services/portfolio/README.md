# Portfolio

Paper positions are rows in the local API database. Each row is a size the desk already calculated. It is not a fill, and it has no broker identity.

There is still no ledger that enforces the daily or weekly loss stops. Do not display those stops as if they already protect an account.

This package does not connect a broker, a wallet, or a bank. The directory is a README only; the routes live in the API. Broker positions, if a MAC-01 run ever stores them, are in the MAC-01 ledger, not in this table. None have been stored.
