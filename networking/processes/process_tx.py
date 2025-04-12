import logging
from blockchain.transaction import Transaction
from networking.messages.envelope import MessageEnvelope
from networking.peer import Peer

### WHAT
## IS
# LOGGING

def process_tx(peer: Peer, menv: MessageEnvelope):
    """
    1. Validate transaction (syntax, signatures).
    2. If valid, insert into mempool.
    3. Broadcast inv for this new tx to other peers.
    """
    try:
        # Parse the transaction from the message envelope
        tx = Transaction.parse(menv.payload_stream)

        # Validate the transaction
        if not validate_transaction(tx):
            logging.error(f"Transaction {tx.hash().hex()} is invalid")
            return

        # Insert into mempool (not implemented here)
        # mempool.add(tx)

        # Broadcast the transaction to other peers (not implemented here)
        # broadcast_inv(tx)

    except Exception as e:
        logging.exception(f"Error processing transaction: {e}")

def validate_transaction(tx: Transaction) -> bool:
    try:
        # Basic sanity checks
        if not tx.inputs or not tx.outputs:
            raise ValueError("Transaction must have inputs and outputs")

        # Check for negative outputs
        for output in tx.outputs:
            if output.value < 0:
                raise ValueError(f"Negative output value: {output.value}")

        # More validation...

        return True

    except ValueError as e:
        # Log specific validation errors for debugging
        logging.error(f"Transaction {tx.hash().hex()} validation error: {str(e)}")
        return False

    except Exception as e:
        # Unexpected errors should be logged with more detail
        logging.exception(f"Unexpected error validating transaction {tx.hash().hex()}")
        return False
