import io
from PIL import Image, ImageDraw, ImageFont
from django.http import HttpResponse
from .models import Raffle
from django.shortcuts import get_object_or_404
from django.conf import settings
import requests

def generate_sharing_card(request, custom_id):
    """Dynamically generate a sharing image for social media."""
    raffle = get_object_or_404(Raffle, custom_id=custom_id)
    
    # Create Canvas
    width, height = 1200, 630
    img = Image.new('RGB', (width, height), color='#0A0F12')
    draw = ImageDraw.Draw(img)
    
    # Hero Color
    draw.ellipse([800, -200, 1400, 400], fill='#A2F62522') # Subtle glow
    
    try:
        # Load Fonts (Using standard paths or fallback)
        # In a real windows env, fonts are in C:\Windows\Fonts
        font_main = ImageFont.truetype("arial.ttf", 80)
        font_sub = ImageFont.truetype("arial.ttf", 40)
        font_price = ImageFont.truetype("arial.ttf", 60)
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_price = ImageFont.load_default()

    # Draw Text
    draw.text((80, 150), "JOIN THE RAFFLE", fill="#A2F625", font=font_sub)
    draw.text((80, 220), raffle.title.upper(), fill="white", font=font_main)
    draw.text((80, 450), f"TICKET: N{raffle.price:,.0f}", fill="white", font=font_price)
    
    # Logo Placeholder
    draw.rectangle([1000, 50, 1150, 150], fill="#A2F625")
    draw.text((1010, 80), "RAFFLE", fill="black", font=ImageFont.load_default())

    # Save to Buffer
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type="image/png")
