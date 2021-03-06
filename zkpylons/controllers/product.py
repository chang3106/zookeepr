import logging

from pylons import request, response, session, tmpl_context as c
from zkpylons.lib.helpers import redirect_to
from pylons.decorators import validate, jsonify
from pylons.decorators.rest import dispatch_on

from formencode import validators, htmlfill, ForEach
from formencode.variabledecode import NestedVariables

from zkpylons.lib.base import BaseController, render
from zkpylons.lib.ssl_requirement import enforce_ssl
from zkpylons.lib.validators import BaseSchema, ProductCategoryValidator, CeilingValidator, FulfilmentTypeValidator
import zkpylons.lib.helpers as h

from authkit.authorize.pylons_adaptors import authorize
from authkit.permissions import ValidAuthKitUser

from zkpylons.model import meta, FulfilmentType
from zkpylons.model.ceiling import Ceiling
from zkpylons.model.product import Product, ProductInclude
from zkpylons.model.product_category import ProductCategory

log = logging.getLogger(__name__)

class ProductSchema(BaseSchema):
    category = ProductCategoryValidator(not_empty=True)
    fulfilment_type = FulfilmentTypeValidator(not_empty=False)
    display_order = validators.Int(not_empty=True)
    active = validators.Bool()
    description = validators.String(not_empty=True)
    badge_text = validators.String(not_empty=False, if_empty=None)
    cost = validators.Int(min=0, max=20000000)
    auth = validators.String(if_empty=None)
    validate = validators.String(if_empty=None)
    ceilings = ForEach(CeilingValidator())

class NewProductSchema(BaseSchema):
    product = ProductSchema()
    pre_validators = [NestedVariables]

class EditProductSchema(BaseSchema):
    product = ProductSchema()
    pre_validators = [NestedVariables]

class ProductController(BaseController):

    @enforce_ssl(required_all=True)
    def __before__(self, **kwargs):
        c.product_categories = ProductCategory.find_all()
        c.fulfilment_types = FulfilmentType.find_all()
        c.ceilings = Ceiling.find_all()

    @authorize(h.auth.has_organiser_role)
    @dispatch_on(POST="_new") 
    def new(self, cat_id=None):
        form=render('/product/new.mako')
        if cat_id is None:
            return form
        else:
            return htmlfill.render(form, {
                'product.category': cat_id,
                'product.category_id': cat_id})

    @authorize(h.auth.has_organiser_role)
    @validate(schema=NewProductSchema(), form='new', post_only=True, on_get=True, variable_decode=True)
    def _new(self):
        results = self.form_result['product']

        c.product = Product(**results)
        meta.Session.add(c.product)
        meta.Session.commit()

        h.flash("Product created")
        redirect_to(action='view', id=c.product.id)

    @authorize(h.auth.has_organiser_role)
    def view(self, id):
        c.can_edit = True
        c.product = Product.find_by_id(id)
        return render('/product/view.mako')

    @authorize(h.auth.has_organiser_role)
    def index(self):
        c.can_edit = True
        return render('/product/list.mako')

    @authorize(h.auth.has_organiser_role)
    @dispatch_on(POST="_edit") 
    def edit(self, id):
        c.product = Product.find_by_id(id)

        defaults = h.object_to_defaults(c.product, 'product')
        defaults['product.category'] = c.product.category.id
        if c.product.fulfilment_type:
            defaults['product.fulfilment_type'] = c.product.fulfilment_type.id

        defaults['product.ceilings'] = []
        for ceiling in c.product.ceilings:
            defaults['product.ceilings'].append(ceiling.id)

        form = render('/product/edit.mako')
        return htmlfill.render(form, defaults)

    @authorize(h.auth.has_organiser_role)
    @validate(schema=EditProductSchema(), form='edit', post_only=True, on_get=True, variable_decode=True)
    def _edit(self, id):
        product = Product.find_by_id(id)

        for key in self.form_result['product']:
            setattr(product, key, self.form_result['product'][key])

        # update the objects with the validated form data
        meta.Session.commit()
        h.flash("The product has been updated successfully.")
        redirect_to(action='view', id=id)

    @authorize(h.auth.has_organiser_role)
    @dispatch_on(POST="_delete") 
    def delete(self, id):
        """Delete the product

        GET will return a form asking for approval.

        POST requests will delete the item.
        """
        c.product = Product.find_by_id(id)
        return render('/product/confirm_delete.mako')

    @authorize(h.auth.has_organiser_role)
    @validate(schema=None, form='delete', post_only=True, on_get=True, variable_decode=True)
    def _delete(self, id):
        c.product = Product.find_by_id(id)
        for include in ProductInclude.find_by_product(id):
            meta.Session.delete(include)
        meta.Session.commit()
        meta.Session.delete(c.product)
        meta.Session.commit()

        h.flash("Product has been deleted.")
        redirect_to('index')

    @authorize(h.auth.Or(h.auth.has_organiser_role, h.auth.has_checkin_role))
    @jsonify
    def json(self):
        c.product_categories = ProductCategory.find_all()
        result = []
        for category in c.product_categories:
            for product in category.products:
                product_dict = {
                    'id': product.id,
                     'category': category.name,
                     'category_order': category.display_order,
                     'product_order': product.display_order,
                     'cost': product.cost,
                     'description': product.description
                }
                result.append(product_dict)
        return { 'r': result }
