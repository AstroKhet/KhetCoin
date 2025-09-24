from unittest import TestCase
from io import BytesIO
from utils.helper import *
from utils.fmt import print_compare_bytes
from blockchain.transaction import *

## Imported from "Programming Bitcoin" by Jimmy Song

class TxTest(TestCase):

    def test_parse_version(self):
        raw_tx = bytes.fromhex(
            "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
        )
        stream = BytesIO(raw_tx)
        tx = Transaction.parse(stream)
        self.assertEqual(tx.version, 1)

    def test_parse_inputs(self):
        raw_tx = bytes.fromhex(
            "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
        )
        stream = BytesIO(raw_tx)
        tx = Transaction.parse(stream)
        self.assertEqual(len(tx.inputs), 1)
        want = bytes.fromhex(
            "d1c789a9c60383bf715f3f6ad9d14b91fe55f3deb369fe5d9280cb1a01793f81"
        )
        self.assertEqual(tx.inputs[0].prev_tx_hash, want)
        self.assertEqual(tx.inputs[0].prev_index, 0)
        want = bytes.fromhex(
            "6b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278a"
        )
        self.assertEqual(tx.inputs[0].script_sig.serialize(), want)
        self.assertEqual(tx.inputs[0].sequence, 0xFFFFFFFE)

    def test_parse_outputs(self):
        raw_tx = bytes.fromhex(
            "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
        )
        stream = BytesIO(raw_tx)
        tx = Transaction.parse(stream)
        self.assertEqual(len(tx.outputs), 2)
        want = 32454049
        self.assertEqual(tx.outputs[0].value, want)
        want = bytes.fromhex("1976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac")
        self.assertEqual(tx.outputs[0].script_pubkey.serialize(), want)
        want = 10011545
        self.assertEqual(tx.outputs[1].value, want)
        want = bytes.fromhex("1976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac")
        self.assertEqual(tx.outputs[1].script_pubkey.serialize(), want)

    def test_parse_locktime(self):
        raw_tx = bytes.fromhex(
            "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
        )
        stream = BytesIO(raw_tx)
        tx = Transaction.parse(stream)
        self.assertEqual(tx.locktime, 410393)

    def test_serialize(self):
        raw_tx = bytes.fromhex(
            "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
        )
        stream = BytesIO(raw_tx)
        tx = Transaction.parse(stream)
        self.assertEqual(tx.serialize(), raw_tx)

    # def test_input_value(self):
    #     tx_hash = "d1c789a9c60383bf715f3f6ad9d14b91fe55f3deb369fe5d9280cb1a01793f81"
    #     index = 0
    #     want = 42505594
    #     tx_in = TransactionInput(bytes.fromhex(tx_hash), index)
    #     self.assertEqual(tx_in.value(), want)

    # def test_input_pubkey(self):
    #     tx_hash = "d1c789a9c60383bf715f3f6ad9d14b91fe55f3deb369fe5d9280cb1a01793f81"
    #     index = 0
    #     tx_in = TransactionInput(bytes.fromhex(tx_hash), index)
    #     want = bytes.fromhex("1976a914a802fc56c704ce87c42d7c92eb75e7896bdc41ae88ac")
    #     self.assertEqual(tx_in.script_pubkey().serialize(), want)

    # def test_fee(self):
    #     raw_tx = bytes.fromhex(
    #         "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
    #     )
    #     stream = BytesIO(raw_tx)
    #     tx = Transaction.parse(stream)
    #     self.assertEqual(tx.fee(), 40000)
    #     raw_tx = bytes.fromhex(
    #         "010000000456919960ac691763688d3d3bcea9ad6ecaf875df5339e148a1fc61c6ed7a069e010000006a47304402204585bcdef85e6b1c6af5c2669d4830ff86e42dd205c0e089bc2a821657e951c002201024a10366077f87d6bce1f7100ad8cfa8a064b39d4e8fe4ea13a7b71aa8180f012102f0da57e85eec2934a82a585ea337ce2f4998b50ae699dd79f5880e253dafafb7feffffffeb8f51f4038dc17e6313cf831d4f02281c2a468bde0fafd37f1bf882729e7fd3000000006a47304402207899531a52d59a6de200179928ca900254a36b8dff8bb75f5f5d71b1cdc26125022008b422690b8461cb52c3cc30330b23d574351872b7c361e9aae3649071c1a7160121035d5c93d9ac96881f19ba1f686f15f009ded7c62efe85a872e6a19b43c15a2937feffffff567bf40595119d1bb8a3037c356efd56170b64cbcc160fb028fa10704b45d775000000006a47304402204c7c7818424c7f7911da6cddc59655a70af1cb5eaf17c69dadbfc74ffa0b662f02207599e08bc8023693ad4e9527dc42c34210f7a7d1d1ddfc8492b654a11e7620a0012102158b46fbdff65d0172b7989aec8850aa0dae49abfb84c81ae6e5b251a58ace5cfeffffffd63a5e6c16e620f86f375925b21cabaf736c779f88fd04dcad51d26690f7f345010000006a47304402200633ea0d3314bea0d95b3cd8dadb2ef79ea8331ffe1e61f762c0f6daea0fabde022029f23b3e9c30f080446150b23852028751635dcee2be669c2a1686a4b5edf304012103ffd6f4a67e94aba353a00882e563ff2722eb4cff0ad6006e86ee20dfe7520d55feffffff0251430f00000000001976a914ab0c0b2e98b1ab6dbf67d4750b0a56244948a87988ac005a6202000000001976a9143c82d7df364eb6c75be8c80df2b3eda8db57397088ac46430600"
    #     )
    #     stream = BytesIO(raw_tx)
    #     tx = Transaction.parse(stream)
    #     self.assertEqual(tx.fee(), 140500)

    # def test_sig_hash(self):
    #     tx = Transaction(
    #         version=1,
    #         inputs=[
    #             TransactionInput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff"
    #                     )
    #                 )
    #             )
    #         ],
    #         outputs=[
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac"
    #                     )
    #                 )
    #             ),
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac"
    #                     )
    #                 )
    #             ),
    #         ],
    #         locktime=410393,
    #     )
    #     want = bytes.fromhex(
    #         "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000001976a914a802fc56c704ce87c42d7c92eb75e7896bdc41ae88acfeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac1943060001000000"
    #     )

    #     mine = tx.serialize_for_signing(0)
    #     print()
    #     print_compare_bytes(want, mine)
    #     self.assertEqual(tx.serialize_for_signing(0), want)

    # def test_verify_p2pkh(self):
    #     tx = Transaction(
    #         version=1,
    #         inputs=[
    #             TransactionInput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff"
    #                     )
    #                 )
    #             )
    #         ],
    #         outputs=[
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac"
    #                     )
    #                 )
    #             ),
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac"
    #                     )
    #                 )
    #             ),
    #         ],
    #         locktime=410393,
    #     )
    #     self.assertTrue(tx.verify())
    #     tx = Transaction(
    #         version=1,
    #         inputs=[
    #             TransactionInput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "48dcc16482f5c835828020498ec1c35f48a578585721b5a77445a4ce93334d18000000006a4730440220636b9f822ea2f85e6375ecd066a49cc74c20ec4f7cf0485bebe6cc68da92d8ce022068ae17620b12d99353287d6224740b585ff89024370a3212b583fb454dce7c160121021f955d36390a38361530fb3724a835f4f504049492224a028fb0ab8c063511a7ffffffff"
    #                     )
    #                 )
    #             )
    #         ],
    #         outputs=[
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "20960705000000001976a914d23541bd04c58a1265e78be912e63b2557fb439088ac"
    #                     )
    #                 )
    #             ),
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "a0860100000000001976a91456d95dc3f2414a210efb7188d287bff487df96c688ac"
    #                     )
    #                 )
    #             ),
    #         ],
    #         locktime=0,
    #     )
    #     self.assertTrue(tx.verify())

    # def test_verify_p2sh(self):
    #     tx = Transaction(
    #         version=1,
    #         inputs=[
    #             TransactionInput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "868278ed6ddfb6c1ed3ad5f8181eb0c7a385aa0836f01d5e4789e6bd304d87221a000000db00483045022100dc92655fe37036f47756db8102e0d7d5e28b3beb83a8fef4f5dc0559bddfb94e02205a36d4e4e6c7fcd16658c50783e00c341609977aed3ad00937bf4ee942a8993701483045022100da6bee3c93766232079a01639d07fa869598749729ae323eab8eef53577d611b02207bef15429dcadce2121ea07f233115c6f09034c0be68db99980b9a6c5e75402201475221022626e955ea6ea6d98850c994f9107b036b1334f18ca8830bfff1295d21cfdb702103b287eaf122eea69030a0e9feed096bed8045c8b98bec453e1ffac7fbdbd4bb7152aeffffffff"
    #                     )
    #                 )
    #             )
    #         ],
    #         outputs=[
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "d3b11400000000001976a914904a49878c0adfc3aa05de7afad2cc15f483a56a88ac"
    #                     )
    #                 )
    #             ),
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "7f400900000000001976a914418327e3f3dda4cf5b9089325a4b95abdfa0334088ac"
    #                     )
    #                 )
    #             ),
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "7f400900000000001976a914418327e3f3dda4cf5b9089325a4b95abdfa0334088ac"
    #                     )
    #                 )
    #             ),
    #             TransactionOutput.parse(
    #                 BytesIO(
    #                     bytes.fromhex(
    #                         "dc4ace020000000017a91474d691da1574e6b3c192ecfb52cc8984ee7b6c5687"
    #                     )
    #                 )
    #             ),
    #         ],
    #         locktime=0,
    #     )

    #     self.assertTrue(tx.verify())

    # def test_sign_input(self):
    #     private_key = PrivateKey(secret=8675309)
    #     stream = BytesIO(
    #         bytes.fromhex(
    #             "010000000199a24308080ab26e6fb65c4eccfadf76749bb5bfa8cb08f291320b3c21e56f0d0d00000000ffffffff02408af701000000001976a914d52ad7ca9b3d096a38e752c2018e6fbc40cdf26f88ac80969800000000001976a914507b27411ccf7f16f10297de6cef3f291623eddf88ac00000000"
    #         )
    #     )
    #     tx_obj = Transaction.parse(stream, testnet=True)
    #     self.assertTrue(tx_obj.sign_input(0, private_key))
    #     want = "010000000199a24308080ab26e6fb65c4eccfadf76749bb5bfa8cb08f291320b3c21e56f0d0d0000006b4830450221008ed46aa2cf12d6d81065bfabe903670165b538f65ee9a3385e6327d80c66d3b502203124f804410527497329ec4715e18558082d489b218677bd029e7fa306a72236012103935581e52c354cd2f484fe8ed83af7a3097005b2f9c60bff71d35bd795f54b67ffffffff02408af701000000001976a914d52ad7ca9b3d096a38e752c2018e6fbc40cdf26f88ac80969800000000001976a914507b27411ccf7f16f10297de6cef3f291623eddf88ac00000000"
    #     self.assertEqual(tx_obj.serialize().hex(), want)

    # def test_is_coinbase(self):
    #     raw_tx = bytes.fromhex(
    #         "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff5e03d71b07254d696e656420627920416e74506f6f6c20626a31312f4542312f4144362f43205914293101fabe6d6d678e2c8c34afc36896e7d9402824ed38e856676ee94bfdb0c6c4bcd8b2e5666a0400000000000000c7270000a5e00e00ffffffff01faf20b58000000001976a914338c84849423992471bffb1a54a8d9b1d69dc28a88ac00000000"
    #     )
    #     stream = BytesIO(raw_tx)
    #     tx = Transaction.parse(stream)
    #     self.assertTrue(tx.is_coinbase())

    # def test_coinbase_height(self):
    #     raw_tx = bytes.fromhex(
    #         "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff5e03d71b07254d696e656420627920416e74506f6f6c20626a31312f4542312f4144362f43205914293101fabe6d6d678e2c8c34afc36896e7d9402824ed38e856676ee94bfdb0c6c4bcd8b2e5666a0400000000000000c7270000a5e00e00ffffffff01faf20b58000000001976a914338c84849423992471bffb1a54a8d9b1d69dc28a88ac00000000"
    #     )
    #     stream = BytesIO(raw_tx)
    #     tx = Transaction.parse(stream)
    #     self.assertEqual(tx.coinbase_height(), 465879)
    #     raw_tx = bytes.fromhex(
    #         "0100000001813f79011acb80925dfe69b3def355fe914bd1d96a3f5f71bf8303c6a989c7d1000000006b483045022100ed81ff192e75a3fd2304004dcadb746fa5e24c5031ccfcf21320b0277457c98f02207a986d955c6e0cb35d446a89d3f56100f4d7f67801c31967743a9c8e10615bed01210349fc4e631e3624a545de3f89f5d8684c7b8138bd94bdd531d2e213bf016b278afeffffff02a135ef01000000001976a914bc3b654dca7e56b04dca18f2566cdaf02e8d9ada88ac99c39800000000001976a9141c4bc762dd5423e332166702cb75f40df79fea1288ac19430600"
    #     )
    #     stream = BytesIO(raw_tx)
    #     tx = Transaction.parse(stream)
    #     self.assertIsNone(tx.coinbase_height())


if __name__ == "__main__":
    TxTest().main()
