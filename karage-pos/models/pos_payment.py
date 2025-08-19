from odoo import models, fields, api, _


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    # Karage-specific payment fields
    karage_payment_mode = fields.Integer(
        string='Karage Payment Mode',
        help='Original payment mode from Karage POS system'
    )
    karage_card_data = fields.Text(
        string='Karage Card Data',
        help='Additional card information from Karage POS'
    )
    card_type = fields.Char(
        string='Card Type',
        help='Type of card used for payment (Cash, Credit, Debit, etc.)'
    )
    cardholder_name = fields.Char(
        string='Cardholder Name',
        help='Name of the cardholder'
    )
    transaction_id = fields.Char(
        string='Transaction ID',
        help='Transaction or card number reference'
    )

    @api.model
    def create_from_karage_data(self, pos_order, payment_detail):
        """
        Create POS payment from Karage payment data
        
        Args:
            pos_order: The POS order to attach payment to
            payment_detail: Payment information from Karage API
            
        Returns:
            pos.payment: Created payment record
        """
        payment_method = self._get_karage_payment_method(payment_detail)
        amount_paid = payment_detail.get('AmountPaid', 0)
        
        payment_vals = {
            'pos_order_id': pos_order.id,
            'payment_method_id': payment_method.id,
            'amount': amount_paid,
            'card_type': payment_detail.get('CardType', ''),
            'cardholder_name': payment_detail.get('CardHolderName', ''),
            'transaction_id': payment_detail.get('CardNumber', ''),
            'karage_payment_mode': payment_detail.get('PaymentMode', 0),
            'karage_card_data': str(payment_detail),
        }
        
        return self.create(payment_vals)

    def _get_karage_payment_method(self, payment_detail):
        """Get appropriate payment method based on Karage payment data"""
        card_type = payment_detail.get('CardType', '').lower()
        payment_mode = payment_detail.get('PaymentMode', 1)
        
        # Map Karage payment types to POS payment methods
        try:
            if payment_mode == 1 or 'cash' in card_type:
                return self.env.ref('karage-pos.payment_method_cash_karage')
            elif payment_mode == 2 or 'card' in card_type or 'credit' in card_type or 'debit' in card_type:
                return self.env.ref('karage-pos.payment_method_card_karage')
            elif 'check' in card_type:
                return self.env.ref('karage-pos.payment_method_check_karage')
            else:
                # Default to cash for unknown payment types
                return self.env.ref('karage-pos.payment_method_cash_karage')
        except ValueError:
            # If payment methods don't exist, find or create a basic cash method
            cash_method = self.env['pos.payment.method'].search([('name', '=', 'Cash')], limit=1)
            if not cash_method:
                # Create a basic cash journal first
                cash_journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
                if not cash_journal:
                    cash_journal = self.env['account.journal'].create({
                        'name': 'Cash',
                        'code': 'CSH1',
                        'type': 'cash',
                    })
                
                # Create cash payment method
                cash_method = self.env['pos.payment.method'].create({
                    'name': 'Cash',
                    'is_cash_count': True,
                    'cash_journal_id': cash_journal.id,
                })
            
            return cash_method