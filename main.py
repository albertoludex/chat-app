#para ver los usuarios que tenemos creados tenemos que entrar: http://localhost:5000/ver_usuarios
#git status
#git add .
#git commit -m "mensaje cambios"
#git push 

#para clonar el repositorio primero ve a ruta donde quieres clonarlo
#segundo git clone (url del repositorio)
#tercero cd (nombre del repositorio)

# Importamos las librerías necesarias
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import join_room, emit
from flask_socketio import SocketIO, send
from sqlite3 import IntegrityError
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
import random
import itsdangerous
active_users = set()
app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

# Creamos una nueva aplicación Flask y configuramos la clave secreta
app.config['SECRET_KEY'] = os.urandom(24)

mail = Mail(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

socketio = SocketIO(app)

# Función para crear una conexión con la base de datos
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Función para crear la tabla de usuarios si no existe
def create_table():
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT)')  # Crea la tabla si no existe
    conn.commit()
    conn.close()

#Aqui empieza el codigo para la recuperacion de contraseña
@app.route('/solicitar_recuperacion', methods=['GET', 'POST'])
def solicitar_recuperacion():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user:
            token = s.dumps(email, salt='recover-key')
            msg = Message('Recuperar contraseña', sender='friunitsoporte@gmail.com', recipients=[email])
            link = url_for('recuperar_contrasena', token=token, _external=True)#aqui se esta generando la URL
            msg.body = 'Haz click en el siguiente enlace para restablecer tu contraseña: {}'.format(link)
            try:
                mail.send(msg)
                print("Correo enviado exitosamente")
            except Exception as e:
                print("Hubo un error al enviar el correo: ", e)
            return render_template('solicitar_recuperacion.html', success='Te hemos enviado un correo electrónico con instrucciones para restablecer tu contraseña, EL CODIGO EXPIRA EN 10 MINUTOS')
        else:
            return render_template('solicitar_recuperacion.html', error='Correo no encontrado en la base de datos')

    return render_template('solicitar_recuperacion.html')
@app.route('/recuperar_contrasena/<token>', methods=['GET', 'POST'])
def recuperar_contrasena(token):
    error = None
    try:
        email = s.loads(token, salt='recover-key', max_age=600)
    except itsdangerous.SignatureExpired:
        return "El enlace ha expirado", 400
    except itsdangerous.BadTimeSignature:
        return "El enlace ha expirado, vuelva a solicitarlo", 400
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if password != confirm_password:
            error = 'Las contraseñas no coinciden'
        elif user['password'] == password:
            error = 'La nueva contraseña no puede ser la misma que la anterior'
        else:
            conn.execute('UPDATE users SET password = ? WHERE email = ?', (password, email))
            conn.commit()
            conn.close()
            return redirect(url_for('iniciar_sesion'))
    return render_template('recuperar_contrasena.html', error=error, token=token)
# Llamamos a la función para crear la tabla
create_table()

# Ruta para la página de inicio
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ver_usuarios')
def ver_usuarios():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('ver_usuarios.html', users=users)

# Ruta para la página de creación de cuenta
@app.route('/crear_cuenta', methods=['GET', 'POST'])
def crear_cuenta():
    error = None
    success = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user:
            error = 'Error al crear la cuenta: El correo electrónico ya está en uso'
        else:
            try:
                conn.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
                conn.commit()
                success = 'Cuenta creada exitosamente'
            except IntegrityError:
                error = 'Error al crear la cuenta'
            finally:
                conn.close()

    return render_template('crear_cuenta.html', error=error, success=success)

# Ruta para la página de inicio de sesión
@app.route('/iniciar_sesion', methods=['GET', 'POST'])
def iniciar_sesion():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Verificamos si el usuario existe en la base de datos
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            session['user'] = user['id']
            session['email'] = user['email']  # Guardamos el correo electrónico en la sesión
            return redirect(url_for('chat'))
        else:
            flash('Correo o contraseña incorrectos', 'error')

    return render_template('iniciar_sesion.html')

# Ruta para la página de chat
@app.route('/chat')
def chat():
    if 'user' in session:
        return render_template('chat.html')
    else:
        return redirect(url_for('iniciar_sesion'))

# Ruta para cerrar sesión
@app.route('/cerrar_sesion')
def cerrar_sesion():
    session.pop('user', None)
    session.pop('color', None)
    return redirect(url_for('index'))
# Manejador para cuando un usuario se desconecta
# Manejador para cuando un usuario se desconecta
@socketio.on('disconnect')
def handle_disconnect():
    if 'email' in session:
        username = session['email'].split('@')[0]
        active_users.remove(username)
        send({'text': f'{username} se ha desconectado', 'class': 'disconnected-message', 'color': '#FF0000'}, broadcast=True)
        # Emitir la lista actualizada de usuarios activos
        emit('users', list(active_users), broadcast=True)
@app.route('/eliminar_cuenta', methods=['GET', 'POST'])
def eliminar_cuenta():
    if 'user' not in session:
        flash('Debes iniciar sesión para eliminar tu cuenta', 'error')
        return redirect(url_for('iniciar_sesion'))

    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (session['user'],))
    conn.commit()
    conn.close()

    session.pop('user', None)
    session.pop('email', None)

    flash('Tu cuenta ha sido eliminada', 'success')
    return redirect(url_for('iniciar_sesion'))

# Manejador para cuando se envía un mensaje
@socketio.on('message')
@socketio.on('message')
def handle_message(data):
    # Obtiene el nombre de usuario del correo electrónico
    username = session['email'].split('@')[0]

    # Obtiene el color de la sesión
    color = session['color']

    # Envia el mensaje con el color de fondo de la sesión
    emit('message', {'text': f'{username}: {data}', 'class': 'message', 'color': color, 'background': color}, broadcast=True)

# Manejador para cuando un usuario se conecta
@socketio.on('connect')
def handle_connect():
    # Añade al usuario a su propia sala
    join_room(request.sid)

    # Comprueba si el usuario ha iniciado sesión
    if 'email' in session:
        # Obtiene el nombre de usuario del correo electrónico
        username = session['email'].split('@')[0]

        # Genera un color aleatorio y lo almacena en la sesión
        color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        session['color'] = color

        # Envia un mensaje con fondo verde al usuario que se acaba de conectar
        emit('message', {'text': f'{username} conectado', 'class': 'connected-message', 'color': '#008000', 'background': '#008000'}, room=request.sid)

        # Si el usuario no está en la lista de usuarios activos, lo agrega y emite el mensaje azul
        if username not in active_users:
            active_users.add(username)
            emit('users', list(active_users), broadcast=True)

            # Envia un mensaje con fondo azul a todos los demás usuarios
            emit('message', {'text': f'{username} conectado', 'class': 'connected-message', 'color': '#0000FF', 'background': '#0000FF'}, broadcast=True, include_self=False)
        # Envia un mensaje con fondo azul a todos los demás usuarios
@app.route('/usuarios_activos')
def usuarios_activos():
    return render_template('chat.html', users=active_users)

#ruta para cambio de contraseña



# Iniciamos la aplicación
if __name__ == '__main__':
    create_table()
    socketio.run(app, debug=True)



