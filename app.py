import sqlite3
import datetime
from flask import Flask, request, jsonify, render_template, send_file
import cv2
import numpy as np
from ultralytics import YOLO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
# подключаем шрифты, чтоб русский текст в пдф работал
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

# беру модель m (n плохо видит объекты на фоне)
model = YOLO('yolov8m.pt')

# переводим название класса на русский
model.names[1] = 'велосипед'

# создание бд при запуске
conn = sqlite3.connect('history.db')
conn.execute('''CREATE TABLE IF NOT EXISTS requests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, bike_count INTEGER)''')
conn.commit()
conn.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    print("--- пошел запрос ---")
    # print(request.files) # дебаг

    if 'image' not in request.files:
        return jsonify({'error': 'no pic'}), 400

    img_file = request.files['image']

    # обычный cv2.imread тут не пашет, делаю через numpy
    img_bytes = np.frombuffer(img_file.read(), np.uint8)
    frame = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)

    # 1 - это айди велика в датасете
    res = model(frame, classes=[1])

    res[0].names[1] = 'велосипед'

    veliki_count = len(res[0].boxes)
    print("нашли великов:", veliki_count)

    # рисуем рамки
    res_img = res[0].plot()

    # сохраняем результат
    cv2.imwrite('static/result.jpg', res_img)

    # пишем стату в базу
    conn2 = sqlite3.connect('history.db')
    cur2 = conn2.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur2.execute('INSERT INTO requests (timestamp, bike_count) VALUES (?, ?)', (now, veliki_count))
    conn2.commit()
    conn2.close()

    return jsonify({'count': veliki_count})


@app.route('/report', methods=['GET'])
def create_report():
    con = sqlite3.connect('history.db')
    c = con.cursor()
    c.execute('SELECT timestamp, bike_count FROM requests ORDER BY timestamp DESC LIMIT 20')
    data = c.fetchall()
    con.close()

    # print(data)

    pdf_path = 'static/report.pdf'
    c = canvas.Canvas(pdf_path, pagesize=letter)

    # регаем шрифт arial
    pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))

    c.setFont("Arial", 16)
    c.drawString(100, 750, "Отчет: Мониторинг велопарковки")

    c.setFont("Arial", 12)
    y = 700
    c.drawString(100, y, "Дата и время            | Найдено велосипедов")
    c.drawString(100, y - 5, "--------------------------------------------------------")

    y = y - 25

    for row in data:
        c.drawString(100, y, f"{row[0]} | {row[1]} шт.")
        y = y - 20
        # если место кончилось делаем новую страницу
        if y < 50:
            c.showPage()
            c.setFont("Arial", 12)
            y = 750

    c.save()
    return send_file(pdf_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)