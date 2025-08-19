import json
from odoo.tests import TransactionCase, HttpCase


class TestOrderControllerBasic(TransactionCase):
    """Basic tests for the order controller logic"""
    
    def test_simple(self):
        """A very simple test to verify testing works"""
        # This test should always pass
        self.assertTrue(True)
        print("✓ Simple test passed!")
    
    def test_request_log_model(self):
        """Test that we can create request log records"""
        # Create a test log record
        log = self.env['karage.request.logger'].create({
            'url': '/api/karage/handleOrder',
            'headers': '{"Content-Type": "application/json"}',
            'body': '{"ItemID": "TEST123", "OrderID": "ORDER456", "LocationID": "LOC789"}',
        })
        
        # Verify the record was created
        self.assertTrue(log.exists())
        self.assertEqual(log.url, '/api/karage/handleOrder')
        self.assertTrue(log.timestamp)
        print(f"✓ Created log record with ID: {log.id}")


class TestOrderControllerHTTP(HttpCase):
    """HTTP tests for the order controller endpoints"""
    
    def test_handle_order_missing_fields(self):
        """Test order handling with missing required fields"""
        # Test data missing LocationID
        order_data = {
            'ItemID': 'ITEM123',
            'OrderID': 'ORDER456'
        }
        
        # Make POST request to the controller endpoint  
        response = self.url_open(
            '/api/karage/handleOrder',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Parse response JSON
        response_data = response.json()
        
        # Verify response contains error for missing fields
        self.assertIn('error', response_data)
        self.assertIn('Missing fields', response_data['error'])
        self.assertIn('LocationID', response_data['error'])
        print("✓ Missing fields validation test passed!")
    
    def test_handle_order_success(self):
        """Test successful order handling"""
        # Test data with all required fields
        order_data = {
            'ItemID': 'ITEM123',
            'OrderID': 'ORDER456', 
            'LocationID': 'LOC789'
        }
        
        # Make POST request to the controller endpoint
        response = self.url_open(
            '/api/karage/handleOrder',
            data=json.dumps(order_data),
            headers={'Content-Type': 'application/json'}
        )
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Parse response JSON
        response_data = response.json()
        
        # Verify response contains success flag and log_id
        self.assertTrue(response_data.get('success'))
        self.assertIn('log_id', response_data)
        self.assertIn('sale_order_id', response_data)
        print(f"✓ Successful order test passed! Log ID: {response_data.get('log_id')}, Sale Order ID: {response_data.get('sale_order_id')}")
