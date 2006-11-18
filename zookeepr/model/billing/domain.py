class InvoiceItem(object):
    def __repr__(self):
        return '<InvoiceItem id=%r description=%r cost=%r>' % (self.id, self.description, self.cost)

class Invoice(object):
    def __repr__(self):
        return '<Invoice id=%r person=%r>' % (self.id, self.person_id)
