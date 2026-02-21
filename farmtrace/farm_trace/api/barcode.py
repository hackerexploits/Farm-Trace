import frappe
import random
from datetime import date
import barcode
from barcode.writer import ImageWriter


def generate_ean13():
    """Generate random EAN13 number"""
    base = "".join([str(random.randint(0, 9)) for _ in range(12)])
    return base  # python-barcode auto adds checksum


def barcode_exists(code):
    return frappe.db.exists("Barcode", code)


def create_barcode_image(code):
    """Generate barcode PNG and attach file"""

    ean = barcode.get("ean13", code, writer=ImageWriter())

    file_path = f"/tmp/{code}"
    filename = ean.save(file_path)

    with open(filename, "rb") as f:
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"{code}.png",
            "content": f.read(),
            "is_private": 0
        })
        file_doc.save(ignore_permissions=True)

    return file_doc.file_url


@frappe.whitelist()
def generate_barcodes(qty):

    created = 0

    for _ in range(int(qty)):

        # ensure uniqueness
        while True:
            code = generate_ean13()
            if not barcode_exists(code):
                break

        image_url = create_barcode_image(code)

        doc = frappe.get_doc({
            "doctype": "Barcode",
            "barcode": code,
            "date": date.today(),
            "barcode_image": image_url
        })

        doc.insert(ignore_permissions=True)
        created += 1

    frappe.db.commit()

    return created