from io import BytesIO

from reportlab.pdfgen import canvas


class InvoiceService:
    @staticmethod
    async def generate_pdf_bytes(order) -> BytesIO:
        buffer = BytesIO()
        p = canvas.Canvas(buffer)

        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawString(100, 800, f"INVOICE - Order #{order.id}")

        # Customer Info
        p.setFont("Helvetica", 12)
        p.drawString(100, 770, f"Date: {order.paid_at.strftime('%Y-%m-%d %H:%M')}")

        # Items Table
        y = 730
        p.drawString(100, y, "Item")
        p.drawString(400, y, "Price")
        p.line(100, y - 5, 500, y - 5)

        for item in order.items:
            y -= 20
            p.drawString(100, y, f"{item.product.name} (x{item.quantity})")
            p.drawString(400, y, f"N{item.price_at_purchase}")

        # Total
        p.line(100, y - 10, 500, y - 10)
        p.drawString(400, y - 30, f"Total: N{order.total_amount}")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer
