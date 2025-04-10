from utils.helper import *
from utils.print import *
from utils.database import *

from blockchain.block import *
from blockchain.merkle_tree import *
from blockchain.transaction import *
from blockchain.script import *

from crypto.key import *
from crypto.mining import *


names = [
    "Gojo Satoru",
    "Yuji Itadori",
    "Megumi Fushiguro",
    "Nobara Kugisaki",
    "Nanami Kento"
]

for guy in names:
    save_private_key(create_private_key(), guy)
    
