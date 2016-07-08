# -*- coding: utf-8 -*-
# © 2016 ClearCorp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'
    
    STATE_SELECTION = [
        ('draft', 'Budget Request'),
        ('budget_approval', 'Waiting Approval'),
        ('budget_approved', 'Draft Bill'),
        ('sent', 'RFQ Sent'),
        ('published', 'Bill published'),
        ('review', 'Bid review'),
        ('deserted', 'Deserted'),
        ('awarded', 'Awarded'),
        ('ineffectual', 'Ineffectual'),
        ('confirmed', 'Waiting Approval'),
        ('approved', 'Purchase Order'),
        ('except_picking', 'Shipping Exception'),
        ('except_invoice', 'Invoice Exception'),
        ('final_approval', 'Final Approval'),
        ('done', 'Done'),
        ('void', 'Anulled'),
        ('cancel', 'Cancelled')]
    
    _columns = {
        'reserved_amount' : fields.float('Reserved', digits=(12,3), readonly=True, ),
        'budget_move_id': fields.many2one('cash.budget.move', 'Budget move'),
        'state': fields.selection(STATE_SELECTION, 'Status', readonly=True, help="The status of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' status. Then the order has to be confirmed by the user, the status switch to 'Confirmed'. Then the supplier must confirm the order to change the status to 'Approved'. When the purchase order is paid and received, the status becomes 'Done'. If a cancel action occurs in the invoice or in the reception of goods, the status becomes in exception.", select=True),
        'partner_id':fields.many2one('res.partner', 'Supplier', states={
            'deserted': [('readonly', True)],
            'ineffectual': [('readonly', True)],
            'confirmed': [('readonly', True)],
            'approved': [('readonly', True)],
            'except_picking': [('readonly', True)],
            'except_invoice': [('readonly', True)],
            'final_approval': [('readonly', True)],
            'done': [('readonly', True)],
            'void': [('readonly', True)],
            'cancel': [('readonly', True)],
            'awarded': [('required', True)]
        }, change_default=True, track_visibility='always'),
    }
    
    def onchange_plan(self, cr, uid, ids,plan_id, context=None):
        return {'domain': {'program_id': [('plan_id','=',plan_id),], }}
    
    def onchange_program(self, cr, uid, ids,program_id, context=None):
        return {'domain': {'program_line_id': [('program_id','=',program_id),], }}
    
    def action_invoice_create(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        obj_bud_line = self.pool.get('cash.budget.move.line')
        acc_inv_mov = self.pool.get('account.invoice')
        obj_inv_line = self.pool.get('account.invoice.line')
        res = []
        for id in ids:
            if context is None:
                context = {}
            purchase = self.browse(cr, uid, [id], context=context)[0]
            invoice_id = super(purchase_order, self).action_invoice_create(
                cr, uid, [id], context=context)
            res = invoice_id
            move_id = purchase.budget_move_id.id
            acc_inv_mov.write(
                cr, uid, [invoice_id],
                {'from_order': True, 'budget_move_id': move_id})
            obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_execute', context=context)
        return res

    def _prepare_inv_line(self, cr, uid, account_id, order_line, context=None):
        res = super(purchase_order, self)._prepare_inv_line(
            cr, uid, account_id, order_line, context=context)
        res.update({
            'budget_move_line_ids': [
                (6, 0, order_line.budget_move_line_ids.ids)],
            'program_line_id': order_line.program_line_id.id
        })
        return res

    
    def action_mark_budget_approval(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'budget_approval'})
        return True
    
    def action_approve_budget(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        for purchase in self.browse(cr, uid, ids, context=context):
            reserved_amount = purchase.amount_total
            if reserved_amount != 0.0:
                move_id = purchase.budget_move_id.id
                obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_reserve', context=context)
                self.write(cr, uid, [purchase.id], {'state': 'budget_approved', 'reserved_amount': reserved_amount})
            else:
                raise osv.except_osv(_('Error!'), _('You cannot approve an order with amount zero '))   
        return True
    
    def action_publish(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'published'})
        return True
    
    def action_review(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'review'})
        return True
    
    def action_award(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        for purchase in self.browse(cr, uid, ids, context=context):
            if not purchase.order_line:
                raise osv.except_osv(_('Error!'),_('You cannot confirm a purchase order without any purchase order line.'))
            move_id = purchase.budget_move_id.id
            obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_compromise', context=context)
        self.write(cr, uid, ids, {'state': 'awarded'})
        return True
    
    def action_desert(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        for purchase in self.browse(cr, uid, ids, context=context):
            move_id = purchase.budget_move_id.id
            obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_cancel', context=context)
        self.write(cr, uid, ids, {'state': 'deserted'})
        return True
    
    def action_ineffectual(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        for purchase in self.browse(cr, uid, ids, context=context):
            move_id = purchase.budget_move_id.id
            obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_cancel', context=context) 
        self.write(cr, uid, ids, {'state': 'ineffectual'})
        return True
    
    def action_final_approval(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'final_approval'})
        return True
    
    def action_void(self, cr, uid, ids, context=None):
        amld_obj = self.pool.get('account.move.line.distribution')
        self.write(cr, uid, ids, {'state': 'void'})
        for purchase in self.browse(cr, uid, ids, context=context):
            bud_move = purchase.budget_move_id
            if bud_move:
                for bud_line in bud_move.move_lines:
                     amld_obj.create(cr, uid, {'distribution_percentage':100.0, 'distribution_amount':bud_line.compromised, 'target_budget_move_line_id':bud_line.id, 'account_move_line_type': 'void'})
            obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_execute', context=context)
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        for purchase in self.browse(cr, uid, ids, context=context):
            bud_move = purchase.budget_move_id
            move_id = bud_move.id
            obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_cancel', context=context)
        self.write(cr, uid, ids, {'state': 'cancel'})
        super(purchase_order, self).action_cancel(cr, uid, ids, context=context)
		
    
    def action_draft(self, cr, uid, ids, context=None):
        obj_bud_mov = self.pool.get('cash.budget.move')
        for purchase in self.browse(cr, uid, ids, context=context):
            bud_move = purchase.budget_move_id
            if bud_move:
                move_id = purchase.budget_move_id.id
                obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_draft', context=context)

        self.write(cr, uid, ids, {'state': 'draft'})
    
    def create_budget_move(self,cr, uid, vals, context=None):
        bud_move_obj = self.pool.get('cash.budget.move')
        move_id = bud_move_obj.create(cr, uid, { 'type':'invoice_in' ,}, context=context)
        return move_id
    
    def create(self, cr, uid, vals, context=None):
        obj_bud_move = self.pool.get('cash.budget.move')
        move_id = self.create_budget_move(cr, uid, vals, context=context)
        vals['budget_move_id'] = move_id
        order_id =  super(purchase_order, self).create(cr, uid, vals, context=context)
        for order in self.browse(cr,uid,[order_id], context=context):
            obj_bud_move.write(cr, uid, [move_id], {'origin': order.name,}, context=context)
        return order_id
    
    def write(self, cr, uid, ids, vals, context=None):
        bud_move_obj = self.pool.get('cash.budget.move')
        result = super(purchase_order, self).write(cr, uid, ids, vals, context=context)
        for order in self.browse(cr, uid, ids, context=context):
            move_id = order.budget_move_id.id
            bud_move_obj.write(cr,uid, [move_id], {'date':order.budget_move_id.date},context=context)
        return result
    
    
class purchase_order_line(osv.osv):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'   

    def _subtotal_discounted_taxed(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context): 
            if line.discount > 0:
                price_unit_discount = line.price_unit - (line.price_unit * (line.discount / 100) )
            else:
                price_unit_discount = line.price_unit
            #-----taxes---------------# 
            #taxes must be calculated with unit_price - discount
            amount_discounted_taxed = self.pool.get('account.tax').compute_all(cr, uid, line.taxes_id, price_unit_discount, line.product_qty, line.product_id.id, line.order_id.partner_id)['total_included']
            res[line.id]= amount_discounted_taxed
        return res
       
    def on_change_program_line(self, cr, uid, ids, program_line, context=None):
        if program_line:
            for line in self.pool.get('cash.budget.program.line').browse(cr, uid,[program_line], context=context):
                return {'value': {'line_available':line.available_budget},}
        return {'value': {}}
    
    def _check_no_taxes(self, cr, uid, ids, context=None):
        for line in self.browse(cr,uid,ids,context=context):
            product = line.product_id
            if product.supplier_taxes_id:
                return False
            if product.property_account_expense and product.property_account_expense.tax_ids:
                return False
            elif product.categ_id.property_account_expense_categ and product.categ_id.property_account_expense_categ.tax_ids:
                return False
        return True
    
    def _check_available(self, cr, uid, ids, field_name, args, context=None):
        bud_line_obj = self.pool.get('cash.budget.move.line')
        result ={}
        if ids: 
            for po_line_id in ids:    
                bud_line_ids = bud_line_obj.search(cr, uid, [('po_line_id','=', po_line_id)], context=context)
                for bud_line in bud_line_obj.browse(cr, uid,bud_line_ids, context=context):
                    result[po_line_id] = bud_line.program_line_id.available_budget
        return result
                             
    _columns = {    
    'program_line_id': fields.many2one('cash.budget.program.line', 'Program line', required=True),
    'line_available': fields.function(_check_available,  type='float', method=True, string='Line available',readonly=True),
    'subtotal_discounted_taxed': fields.function(_subtotal_discounted_taxed, digits_compute= dp.get_precision('Account'), string='Subtotal', ),
    'budget_move_line_ids': fields.one2many(
        'cash.budget.move.line', 'po_line_id', string='Budget Move Lines')
    }

    _constraints=[
        (_check_no_taxes, 'Error!\n There is a tax defined for this product, its account or the account of the product category. \n The tax must be included in the price of the product.', []),
        ]

#*************************************************************************************
# Methods used to create budget move lines for the tax amount of each purchase order line
#*************************************************************************************
#    def create_bud_tax_line(self, cr, uid, line_id,vals=None, context=None):
#        bud_line_obj = self.pool.get('cash.budget.move.line')
#        tax_obj = self.pool.get('account.tax')
#        order_line = self.browse(cr, uid, [line_id], context=context)[0]
#        move_id = order_line.order_id.budget_move_id.id
#        program_line_id = vals['program_line_id'] if vals else order_line.program_line_id.id
#        for tax in tax_obj.compute_all(cr, uid, order_line.taxes_id, order_line.price_unit, order_line.product_qty, order_line.product_id, order_line.partner_id)['taxes']:
#            bud_line_obj.create(cr, uid, {'budget_move_id': move_id,
#                                         'origin' : 'Taxes of: ' + order_line.name,
#                                         'program_line_id': program_line_id, 
#                                         'fixed_amount': tax.get('amount', 0.0),
#                                         'po_line_id': order_line.id,
#                                          }, context=context)

#    def write(self, cr, uid, ids, vals, context=None):
#        bud_line_obj = self.pool.get('cash.budget.move.line')
#        bud_move_obj = self.pool.get('cash.budget.move')
#        result = False
#        for line in self.browse(cr, uid, ids, context=context):
#            search_result = bud_line_obj.search(cr, uid,[('po_line_id','=', line.id)], context=context) 
#            bud_lines = bud_line_obj.browse(cr, uid, search_result, context=context)
#            #deleting tax lines
#            for bud_line in bud_lines: 
#                if bud_line.fixed_amount != line.price_subtotal:
#                    bud_line_obj.unlink(cr, uid, [bud_line.id], context=context)
#            #processing PO lines and re-creating taxes
#            for bud_line in bud_lines: 
#                if bud_line.fixed_amount == line.price_subtotal:
#                    result = super(purchase_order_line, self).write(cr, uid, [line.id], vals, context=context)
#                    updated_fields = self.read(cr, uid,[line.id], ['program_line_id', 'price_subtotal'], context=context)[0]
#                    bud_line_obj.write(cr, uid, [bud_line.id], {'program_line_id': updated_fields['program_line_id'][0], 'fixed_amount':updated_fields['price_subtotal']})
#                    self.create_bud_tax_line(cr, uid, line.id, context=None)     
#        return result  
   

    def create_budget_move_line(self,cr, uid, vals, line_id, context=None):
        
        purch_order_obj = self.pool.get('purchase.order')
        purch_line_obj = self.pool.get('purchase.order.line')
        bud_move_obj = self.pool.get('cash.budget.move')
        bud_line_obj = self.pool.get('cash.budget.move.line')
        
        po_id = vals['order_id'] 
        order = purch_order_obj.browse(cr, uid, [po_id], context=context)[0]
        order_line = purch_line_obj.browse(cr, uid, [line_id], context=context)[0]
        move_id = order.budget_move_id.id
        
        
        new_line_id=bud_line_obj.create(cr, uid, {'budget_move_id': move_id,
                                         'origin' : order_line.name,
                                         'program_line_id': vals['program_line_id'], 
                                         'fixed_amount': order_line.price_subtotal,
                                         'po_line_id': line_id,
                                          }, context=context)
        bud_move_obj.recalculate_values(cr, uid, [move_id], context=context)
        return new_line_id
  
    def check_budget_from_po_line(self, cr, uid, po_line_ids, context=None):
        bud_move_obj = self.pool.get('cash.budget.move')
        for order_line in self.browse(cr, uid, po_line_ids, context=context):
            result = bud_move_obj._check_values(cr, uid, [order_line.order_id.budget_move_id.id], context)
            if result[0]:
                return True
            else:
                raise osv.except_osv(_('Error!'), result[1])
            return True
            

    def create(self, cr, uid, vals, context=None):
        line_id =  super(purchase_order_line, self).create(cr, uid, vals, context=context)
        bud_line_id = self.create_budget_move_line(cr, uid, vals, line_id, context=context)
        self.check_budget_from_po_line(cr, uid, [line_id], context)
        return line_id

    def write(self, cr, uid, ids, vals, context=None):
        bud_line_obj = self.pool.get('cash.budget.move.line')
        bud_move_obj = self.pool.get('cash.budget.move')
        moves_to_update = []
        for line in self.browse(cr, uid, ids, context=context):
            search_result = bud_line_obj.search(cr, uid,[('po_line_id','=', line.id)], context=context) 
            bud_lines = bud_line_obj.browse(cr, uid, search_result, context=context)
            for bud_line in bud_lines:
                if bud_line.fixed_amount == line.price_subtotal:
                    if 'price_subtotal' in vals:
                        bud_line_obj.write(cr, uid, [bud_line.id], {'fixed_amount': vals['price_subtotal']})
                        moves_to_update.append(bud_line.budget_move_id.id)
                    if 'price_unit' in vals:
                        bud_line_obj.write(cr, uid, [bud_line.id], {'fixed_amount': vals['price_unit']})
                        moves_to_update.append(bud_line.budget_move_id.id)
                if 'program_line_id' in vals:
                    bud_line_obj.write(cr, uid, [bud_line.id], {'program_line_id': vals['program_line_id']})
                    if bud_line.budget_move_id.id not in moves_to_update:
                        moves_to_update.append(bud_line.budget_move_id.id)
        bud_move_obj.recalculate_values(cr, uid, moves_to_update, context=context)
        self.check_budget_from_po_line(cr, uid, ids, context)
        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

class purchase_line_invoice(osv.osv_memory):

    """ To create invoice for purchase order line"""

    _inherit = 'purchase.order.line_invoice'
    
    def makeInvoices(self, cr, uid, ids, context=None): 
        result = super(purchase_line_invoice, self).makeInvoices(cr, uid, ids, context=context)
        
        record_ids =  context.get('active_ids',[])
        if record_ids:
            obj_bud_mov = self.pool.get('cash.budget.move')
            obj_bud_line = self.pool.get('cash.budget.move.line')
            purchase_line_obj = self.pool.get('purchase.order.line')
            
            invoice_obj = self.pool.get('account.invoice')
            purchase_obj = self.pool.get('purchase.order')
            purchase_line_obj = self.pool.get('purchase.order.line')
            invoice_line_obj = self.pool.get('account.invoice.line')
            
            for po_line in purchase_line_obj.browse(cr, uid, record_ids, context=context):
                asoc_bud_line_id = obj_bud_line.search(cr, uid, [('po_line_id','=',po_line.id), ])[0]
                if po_line.invoice_lines:
                    inv_line = po_line.invoice_lines[0]
                    invoice_line_obj.write(cr, uid, inv_line.id, {'program_line_id': po_line.program_line_id.id}, context=context)
                    obj_bud_line.write(cr, uid, [asoc_bud_line_id],{'inv_line_id': inv_line.id}, context=context)
                    move_id = po_line.order_id.budget_move_id.id
                    invoice_obj.write(cr, uid, [inv_line.invoice_id.id], {'budget_move_id': move_id, 'from_order':True}, context=context)
                    obj_bud_mov.signal_workflow(cr, uid, [move_id], 'button_execute', context=context)
        return result
        
