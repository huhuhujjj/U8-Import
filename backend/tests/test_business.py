import unittest
from app.business.purchase_order import normalize, business_key

class BusinessTests(unittest.TestCase):
    def test_reordered_columns_and_decimal(self):
        self.assertEqual(normalize({'G':'001','K':'2.00','L':'3.50'}, {'inventory_code':'G','quantity':'K','price':'L'}),
                         {'inventory_code':'001','quantity':'2','price':'3.5'})

    def test_invalid_values_rejected(self):
        for q,p in [('0','1'),('-1','1'),('NaN','1'),('1','Infinity'),('1','-1'),('abc','1')]:
            with self.subTest(q=q,p=p), self.assertRaises(ValueError):
                normalize({'i':'A','q':q,'p':p},{'inventory_code':'i','quantity':'q','price':'p'})

    def test_business_identity_changes_between_orders(self):
        self.assertNotEqual(business_key({'order_reference':'A','vendor_code':'V'},'1'),
                            business_key({'order_reference':'B','vendor_code':'V'},'1'))
        self.assertEqual(business_key({'order_reference':'A','vendor_code':'V'},'1'),
                         business_key({'vendor_code':'V','order_reference':'A'},'1'))

if __name__ == '__main__':
    unittest.main()
