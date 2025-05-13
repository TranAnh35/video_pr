import os
from PIL import Image

def extract_image_metadata(image_path):
    """
    Extract technical metadata from an image file (width, height, format, size_bytes)
    
    Args:
        image_path (str): Path to the image file
    
    Returns:
        dict: metadata including width, height, format, size_bytes
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"File not found: {image_path}")

    with Image.open(image_path) as img:
        width, height = img.size
        format = img.format

    size_bytes = os.path.getsize(image_path)

    return {
        'width': width,
        'height': height,
        'format': format,
        'size_bytes': size_bytes
    }


if __name__ == '__main__':
    metadata = extract_image_metadata('E:/Windsurf/Company_Project/Split_sence/src/resource/Images/667626_18933d713e.jpg')
    print(metadata)
    print(metadata['width'])
    print(metadata['height'])
    print(metadata['format'])
    print(metadata['size_bytes'])
    
    