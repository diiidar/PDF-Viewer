from PIL import Image
import cv2
import numpy as np

def preprocess_image(pil_img, center_text=True):
    """
    Preprocesses a scanned document image by deskewing, centering text, and inpainting borders.
    :param pil_img: PIL.Image input
    :param center_text: whether to auto-center text region
    :return: processed PIL.Image
    """
    if not center_text:
        return pil_img

    # Convert to OpenCV image
    img_rgb = np.array(pil_img.convert("RGB"))
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    # Threshold to binary image
    _, binary = cv2.threshold(img_gray, 155, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find text contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return pil_img
    # cv2.imshow('w', binary)
    # cv2.waitKey(0)
    # Bounding box around all contours
    x, y, w, h = cv2.boundingRect(np.vstack(contours))

    # Image size
    img_h, img_w = img_gray.shape
    center_x, center_y = img_w // 2, img_h // 2
    text_center_x, text_center_y = x + w // 2, y + h // 2

    # Calculate shift
    dx = center_x - text_center_x
    dy = center_y - text_center_y

    print("Image center:", center_x, center_y)
    print("Text center:", text_center_x, text_center_y)
    print("dx, dy:", dx, dy)
    print('-'*80)

    # Shift the image
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    shifted_img = cv2.warpAffine(img_rgb, M, (img_w, img_h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    # Mask for white regions (inpainting)
    shifted_gray = cv2.cvtColor(shifted_img, cv2.COLOR_RGB2GRAY)

    # Create mask for very bright regions
    mask = cv2.threshold(shifted_gray, 250, 255, cv2.THRESH_BINARY)[1]
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)

    inpainted = cv2.inpaint(shifted_img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

    return Image.fromarray(inpainted)
