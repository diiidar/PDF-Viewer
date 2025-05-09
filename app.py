from flask import Flask, render_template, request, jsonify, send_file, abort
from pdf2image import convert_from_path
from utils.image_processing import preprocess_image
import os
import cv2 as cv
import numpy as np

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'data', 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'data', 'processed_pages')
CANVAS_FOLDER = os.path.join(BASE_DIR, 'data', 'drawings')
LENGTH = 0

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(CANVAS_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_pdf_route():
    global LENGTH
    file = request.files.get('pdf_file')
    preprocessing_enabled = request.form.get('preprocessing') == '1'

    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    clear_folder(PROCESSED_FOLDER)
    clear_folder(CANVAS_FOLDER)

    processed_pages = process_pdf(filepath, output_folder=PROCESSED_FOLDER, preprocessing=preprocessing_enabled)
    LENGTH = len(processed_pages)
    for page_num in range(1, LENGTH + 1):
        canvas_path = os.path.join(CANVAS_FOLDER, f"page_{page_num}_drawing.png")

        size = cv.imread(os.path.join(PROCESSED_FOLDER, processed_pages[page_num-1])).shape

        if not os.path.exists(canvas_path):
            canvas = np.ones(size, dtype=np.uint8) * 255
            cv.imwrite(canvas_path, canvas)

    return jsonify({"status": "success", "pages": processed_pages})

@app.route('/draw', methods=['POST'])
def draw_on_canvas():
    data = request.get_json()
    page_num = data.get('page_num')
    draw_data = data.get('draw_data')  # List of coordinates or strokes

    if not page_num or not draw_data:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    canvas_path = os.path.join(CANVAS_FOLDER, f"page_{page_num}_drawing.png")
    if not os.path.exists(canvas_path):
        return jsonify({"status": "error", "message": "Canvas not found"}), 404

    canvas = cv.imread(canvas_path)

    for stroke in draw_data:
        for point in stroke:
            x, y = point
            cv.circle(canvas, (x, y), 3, (0, 0, 0), -1)  # Draw black dot

    cv.imwrite(canvas_path, canvas)
    return jsonify({"status": "success", "message": "Drawing updated"})

@app.route('/text', methods=['POST'])
def text_area():
    data = request.get_json()
    page_num = data['page_num']
    text = data['text']
    pos = data['pos']

    if not page_num or not pos:
        return jsonify({"status": "error", "message": "Missing data"}), 400
    img_path = f'data/processed_pages/page_{page_num}.png'
    image = cv.imread(img_path)

    if image is None:
        return jsonify({'status': 'error', 'message': 'Image not found'}), 404

    x, y = pos['x'], pos['y']

    image = cv.putText(image, text, (x,y), cv.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv.LINE_AA)
    composite_path = os.path.join(PROCESSED_FOLDER, f"page_{page_num}.png")
    cv.imwrite(composite_path, image)
    return jsonify({'status': 'success'})

@app.route('/night', methods=['POST'])
def night_on():
    for i in range(1, LENGTH+1):
        composite_path = os.path.join(PROCESSED_FOLDER, f"page_{i}.png")
        image = cv.imread(composite_path, cv.IMREAD_COLOR)

        if image is None:
            return jsonify({'status': 'error', 'message': 'Image not found'}), 404

        image_neg = cv.bitwise_not(image)
        cv.imwrite(composite_path, image_neg)
    return jsonify({'status': 'success'})

@app.route('/highlight', methods=['POST'])
def highlight_area():
    data = request.get_json()
    page_num = data['page_num']
    rect = data['highlight_rect']

    img_path = f'data/processed_pages/page_{page_num}.png'
    image = cv.imread(img_path)

    if image is None:
        return jsonify({'status': 'error', 'message': 'Image not found'}), 404

    x, y = rect['x'], rect['y']
    w, h = rect['width'], rect['height']

    overlay = image.copy()
    cv.rectangle(overlay, (x, y), (x + w, y + h), (5, 250, 250), -1)  # yellow fill

    cv.addWeighted(image, 0.85, overlay, 0.15, 0, image)
    cv.addWeighted(image, 0.85, overlay, 0.15, 0, image)

    cv.imwrite(img_path, image)

    if image is not None:
        composite_path = os.path.join(PROCESSED_FOLDER, f"page_{page_num}.png")
        cv.imwrite(composite_path, image)
    return jsonify({'status': 'success'})

@app.route('/erase', methods=['POST'])
def erase_from_canvas():
    data = request.get_json()
    page_num = data.get('page_num')
    erase_data = data.get('erase_data')  # List of coordinates or strokes

    if not page_num or not erase_data:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    canvas_path = os.path.join(CANVAS_FOLDER, f"page_{page_num}_drawing.png")
    if not os.path.exists(canvas_path):
        return jsonify({"status": "error", "message": "Canvas not found"}), 404

    canvas = cv.imread(canvas_path)

    for stroke in erase_data:
        for point in stroke:
            x, y = point
            cv.circle(canvas, (x, y), 7, (255, 255, 255), -1)  # Erase by drawing white circle

    cv.imwrite(canvas_path, canvas)
    return jsonify({"status": "success", "message": "Erasing updated"})

@app.route('/page/<int:page_num>')
def serve_page(page_num):
    result = generate_page_image(page_num)
    if result is None:
        abort(404)

    temp_path = os.path.join(PROCESSED_FOLDER, f"temp_{page_num}.png")
    cv.imwrite(temp_path, result)
    return send_file(temp_path, mimetype='image/png')

def color_extraction(canvas, processed_page, lowerb, upperb):
    mask = cv.inRange(canvas, lowerb, upperb)

    canvas = cv.cvtColor(canvas, cv.COLOR_BGR2BGRA)

    canvas[:, :, 3] = mask

    bgr_fg = canvas[:, :, :3]
    alpha_fg = canvas[:, :, 3]

    mask_fg = cv.threshold(alpha_fg, 0, 255, cv.THRESH_BINARY)[1]
    mask_bg = cv.bitwise_not(mask_fg)

    bg_part = cv.bitwise_and(processed_page, processed_page, mask=mask_bg)
    fg_part = cv.bitwise_and(bgr_fg, bgr_fg, mask=mask_fg)
    return bg_part, fg_part

@app.route('/favicon.ico')
def favicon():
    return '', 204

def generate_page_image(page_num):
    processed_page_path = os.path.join(PROCESSED_FOLDER, f"page_{page_num}.png")
    canvas_path = os.path.join(CANVAS_FOLDER, f"page_{page_num}_drawing.png")

    if not os.path.exists(processed_page_path):
        return None

    processed_page = cv.imread(processed_page_path)

    if os.path.exists(canvas_path):
        drawing_canvas = cv.imread(canvas_path)

        bg_draw, fg_draw = color_extraction(
            drawing_canvas, processed_page,
            lowerb=(0, 0, 0), upperb=(1, 1, 1)
        )
        result_draw = cv.add(bg_draw, fg_draw)

        return result_draw

    return processed_page

def process_pdf(pdf_path, output_folder, preprocessing=False):
    os.makedirs(output_folder, exist_ok=True)
    images = convert_from_path(pdf_path, dpi=100)

    page_paths = []
    for i, img in enumerate(images):
        if preprocessing:
            print('Page:',i)
            img = preprocess_image(img, center_text=True)  # PIL.Image → PIL.Image

        image_filename = f"page_{i+1}.png"
        image_path = os.path.join(output_folder, image_filename)
        img.save(image_path, 'PNG')
        page_paths.append(image_filename)
    return page_paths

def clear_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

if __name__ == '__main__':
    app.run(debug=True)
