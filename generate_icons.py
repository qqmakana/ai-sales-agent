"""Generate PWA icons for AI Sales Agent"""
import os

# Create a simple SVG icon and convert to PNG using PIL
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

def create_icon(size, output_path):
    """Create a gradient icon with 'AI' text"""
    # Create image with gradient background
    img = Image.new('RGB', (size, size), '#0f172a')
    draw = ImageDraw.Draw(img)
    
    # Draw gradient circle
    center = size // 2
    for i in range(center, 0, -1):
        # Gradient from green to blue
        r = int(16 + (i / center) * 20)
        g = int(185 - (i / center) * 50)
        b = int(129 + (i / center) * 100)
        color = f'#{r:02x}{g:02x}{b:02x}'
        draw.ellipse([center - i, center - i, center + i, center + i], fill=color)
    
    # Draw "AI" text
    try:
        font_size = size // 3
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    text = "AI"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - bbox[1]
    
    draw.text((x, y), text, fill='white', font=font)
    
    # Save
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

# Icon sizes needed for PWA
sizes = [72, 96, 128, 144, 152, 192, 384, 512]

icons_dir = "static/icons"
os.makedirs(icons_dir, exist_ok=True)

for size in sizes:
    output_path = os.path.join(icons_dir, f"icon-{size}.png")
    create_icon(size, output_path)

print("\n✅ All PWA icons created!")
