#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create a garage icon for the api_integration module
Converts SVG to PNG format required by Odoo
"""

try:
    from PIL import Image, ImageDraw
    import os
    
    # Create 128x128 PNG icon
    size = 128
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background - Blue
    draw.rounded_rectangle([0, 0, size, size], radius=8, fill=(74, 144, 226, 255))
    
    # Roof - Red
    roof_points = [(10, 30), (64, 10), (118, 30)]
    draw.polygon(roof_points, fill=(231, 76, 60, 255))
    
    # Garage Door - Dark Blue
    draw.rounded_rectangle([20, 30, 108, 100], radius=4, fill=(44, 62, 80, 255))
    
    # Door Frame
    draw.rounded_rectangle([18, 28, 110, 102], radius=4, outline=(26, 37, 47, 255), width=2)
    
    # Door Divider
    draw.line([64, 30, 64, 100], fill=(52, 73, 94, 255), width=2)
    
    # Left Panel (darker)
    draw.rectangle([22, 32, 62, 100], fill=(52, 73, 94, 76))
    
    # Right Panel (darker)
    draw.rectangle([66, 32, 106, 100], fill=(52, 73, 94, 76))
    
    # Door Handles
    draw.ellipse([32, 62, 38, 68], fill=(236, 240, 241, 255))
    draw.ellipse([90, 62, 96, 68], fill=(236, 240, 241, 255))
    
    # Windows
    draw.rounded_rectangle([30, 45, 42, 57], radius=2, fill=(52, 152, 219, 255))
    draw.rounded_rectangle([86, 45, 98, 57], radius=2, fill=(52, 152, 219, 255))
    
    # Ground
    draw.rectangle([0, 100, size, size], fill=(127, 140, 141, 255))
    
    # API/Integration Symbol (Gear) - Orange
    center_x, center_y = 64, 20
    gear_radius = 8
    inner_radius = 5
    small_radius = 2
    
    # Outer gear circle
    draw.ellipse([center_x - gear_radius, center_y - gear_radius, 
                  center_x + gear_radius, center_y + gear_radius], 
                 fill=(243, 156, 18, 230))
    
    # Inner gear circle
    draw.ellipse([center_x - inner_radius, center_y - inner_radius, 
                  center_x + inner_radius, center_y + inner_radius], 
                 outline=(255, 255, 255, 255), width=2)
    
    # Center dot
    draw.ellipse([center_x - small_radius, center_y - small_radius, 
                  center_x + small_radius, center_y + small_radius], 
                 fill=(255, 255, 255, 255))
    
    # Gear teeth (simplified)
    for angle in [0, 90, 180, 270]:
        import math
        rad = math.radians(angle)
        x1 = center_x + (inner_radius + 1) * math.cos(rad)
        y1 = center_y + (inner_radius + 1) * math.sin(rad)
        x2 = center_x + (gear_radius - 1) * math.cos(rad)
        y2 = center_y + (gear_radius - 1) * math.sin(rad)
        draw.line([x1, y1, x2, y2], fill=(255, 255, 255, 255), width=2)
    
    # Save the icon
    icon_path = os.path.join(os.path.dirname(__file__), 'static', 'description', 'icon.png')
    os.makedirs(os.path.dirname(icon_path), exist_ok=True)
    img.save(icon_path, 'PNG')
    print(f"✓ Icon created successfully at: {icon_path}")
    
except ImportError:
    print("PIL (Pillow) is required. Install it with: pip install Pillow")
    print("Or manually convert the SVG file at static/description/icon.svg to PNG format (128x128 pixels)")
except Exception as e:
    print(f"Error creating icon: {e}")
    print("You can manually convert the SVG file at static/description/icon.svg to PNG format (128x128 pixels)")

