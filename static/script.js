let currentPage = 1;
let totalPages = 0;
let currentZoom = 1;
let currentRotation = 0;
const image = document.getElementById('pdf-page');
image.style.display = 'none';
const form = document.getElementById('form');
const tools = document.getElementById('tools')
const loader = document.getElementById('loading-indicator');
const controls = document.getElementById('controls');
const zoomIn = document.getElementById('zoom-in');
const zoomOut = document.getElementById('zoom-out');
const canvas = document.getElementById('drawing-canvas');
const ctx = canvas.getContext('2d');
let drawing = false;
let drawMode = 'draw'; // or 'erase' or 'highlight'
let strokes = [];
let currentStroke = [];
let highlightStart = null;
let night_mode = false;

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    currentPage = 1;
    totalPages = 0;
    image.style.display = 'none';
    controls.style.display = 'none';
    loader.style.display = 'block';
    currentZoom = 1.0;

    const formData = new FormData(form);
    const preprocessingEnabled = document.getElementById('preprocessing-toggle').checked;
    formData.append('preprocessing', preprocessingEnabled ? '1' : '0');

    const response = await fetch('/process', {
        method: 'POST',
        body: formData
    });

    const result = await response.json();
    if (result.status === 'success') {
        totalPages = result.pages.length;
        currentPage = 1;
        preloadPages(result.pages);
    } else {
        alert('Failed to process PDF');
        loader.style.display = 'none';
    }
});

zoomOut.addEventListener("click", () => {
    currentZoom += 0.1;
    applyZoom();
});

zoomIn.addEventListener("click", () => {
    if (currentZoom > 0.2) {
        currentZoom -= 0.1;
        applyZoom();
    }
});

function showPage(page) {
    image.src = '';
    image.style.display = 'none';
    image.onload = () => {
        const container = document.getElementById('viewer-wrapper');
        const canvas = document.getElementById('drawing-canvas');

        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;

        const naturalWidth = image.naturalWidth;
        const naturalHeight = image.naturalHeight;

        canvas.width = naturalWidth;
        canvas.height = naturalHeight;

        image.style.display = 'block';
        canvas.style.display = 'block';
        applyZoom();
    };
    const timestamp = new Date().getTime();  // Get the current timestamp
    image.src = `/page/${page}?t=${timestamp}`;  // Append timestamp as a query parameter
    currentRotation = 0;
}

function preloadPages(pages) {
    let firstShown = false;
    pages.forEach((_, idx) => {
        const img = new Image();
        img.src = `/page/${idx + 1}`;
        img.onload = () => {
            if (!firstShown && idx === 0) {
                showPage(1);
                loader.style.display = 'none';
                tools.style.display = 'flex'
                controls.style.display = 'flex';
                firstShown = true;
            }
        };
    });
}

function applyZoom() {
    if (!image || !canvas) return;

    image.style.transformOrigin = currentRotation % 360 === 0 ? 'top center' : 'center center';
    image.style.transform = `scale(${currentZoom}) rotate(${currentRotation}deg)`;

    // Adjust canvas transform and size to match zoom
    canvas.style.transformOrigin = image.style.transformOrigin;
    canvas.style.transform = image.style.transform;
}
function toggleNightMode() {
    canvas.style.pointerEvents = 'none';
    const nightModeEnabled = document.getElementById('night-mode-toggle').checked;
    fetch('/night', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            page_num: currentPage
        })
    }).then(res => {
        if (!res.ok) console.error(`Failed to toggle Night Mode`);
    });
    setTimeout(() => showPage(currentPage), 200);
}

function rotatePage() {
    canvas.style.pointerEvents = 'none';
    if (!image || !canvas) return;
    image.style.transformOrigin = "center center";
    currentRotation += 90;
    if (currentRotation >= 360){ currentRotation %= 360;}
    image.style.transform = `scale(${currentZoom}) rotate(${currentRotation}deg)`;
    canvas.style.transform = image.style.transform;
}

document.addEventListener('keydown', (e) => {
    if (totalPages === 0) return;
    if (e.key === 'ArrowRight' && currentPage < totalPages) {
        currentPage++;
        showPage(currentPage);
    } else if (e.key === 'ArrowLeft' && currentPage > 1) {
        currentPage--;
        showPage(currentPage);
    }
});

function resizeCanvasToMatchImage() {
    canvas.width = image.clientWidth;
    canvas.height = image.clientHeight;
    canvas.style.width = image.clientWidth + 'px';
    canvas.style.height = image.clientHeight + 'px';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
}

function setMode(mode) {
    drawMode = mode;
    canvas.style.pointerEvents = 'auto';
}

canvas.addEventListener('mousedown', (e) => {
    const pos = getMousePos(e);
    if (drawMode === 'highlight') {
        highlightStart = pos;
    } else if (drawMode === 'text') {
        sendTextToServer(pos);
    } else {
        drawing = true;
        currentStroke = [];
        drawDot(pos.x, pos.y);
        currentStroke.push([pos.x, pos.y]);
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (drawMode === 'text') return;
    if (drawMode === 'highlight') return;
    if (!drawing) return;
    const pos = getMousePos(e);
    drawDot(pos.x, pos.y);
    currentStroke.push([pos.x, pos.y]);
});

canvas.addEventListener('mouseup', (e) => {
    const pos = getMousePos(e);
    if (drawMode === 'text') return;
    if (drawMode === 'highlight' && highlightStart) {
        const x = Math.min(highlightStart.x, pos.x);
        const y = Math.min(highlightStart.y, pos.y);
        const width = Math.abs(highlightStart.x - pos.x);
        const height = Math.abs(highlightStart.y - pos.y);
        const highlightRect = { x, y, width, height };
        sendHighlightToServer(highlightRect);
        highlightStart = null;
    } else if (drawing && currentStroke.length > 0) {
        strokes.push(currentStroke);
        sendStrokeToServer(currentStroke);
    }
    drawing = false;
});

function getMousePos(evt) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: Math.round((evt.clientX - rect.left) * (canvas.width / rect.width)),
        y: Math.round((evt.clientY - rect.top) * (canvas.height / rect.height))
    };
}

function drawDot(x, y) {
    ctx.fillStyle = drawMode === 'draw' ? 'black' : 'white';
    ctx.beginPath();
    ctx.arc(x, y, 2, 0, 2 * Math.PI);
    ctx.fill();
}

function sendStrokeToServer(stroke) {
    const route = drawMode === 'draw' ? '/draw' : '/erase';

    fetch(route, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            page_num: currentPage,
            [drawMode === 'draw' ? 'draw_data' : 'erase_data']: [stroke]
        })
    }).then(res => {
        if (!res.ok) console.error(`Failed to send ${drawMode} stroke`);
    });
    setTimeout(() => showPage(currentPage), 100);
}

function sendHighlightToServer(rect) {
    fetch('/highlight', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            page_num: currentPage,
            highlight_rect: rect
        })
    }).then(res => {
        if (!res.ok) console.error('Failed to send highlight');
    });
        setTimeout(() => showPage(currentPage), 100);

}

function sendTextToServer(pos) {
    const userText = prompt("Enter your text:");
    if (!userText) return;
    fetch('/text', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            page_num: currentPage,
            text: userText,
            pos: pos
        })
    }).then(res => {
        if (!res.ok) console.error('Failed to send highlight');
    });
        setTimeout(() => showPage(currentPage), 100);

}


function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

image.onload = () => {
    resizeCanvasToMatchImage();
    clearCanvas();
};