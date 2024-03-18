#para ver los usuarios que tenemos creados tenemos que entrar: http://localhost:5000/ver_usuarios
#git status
#git add .
#git commit -m "mensaje cambios"
#git push 

# Importamos las librerías necesarias
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import join_room, emit
from flask_socketio import SocketIO, send
from sqlite3 import IntegrityError
import sqlite3
import os
import random

# Creamos una nueva aplicación Flask y configuramos la clave secreta
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
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
@socketio.on('disconnect')
def handle_disconnect():
    send({'text': 'Usuario desconectado', 'color': '#FF0000'}, broadcast=True)


@app.route('/eliminar_cuenta', methods=['POST'])
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

# Manejador para los mensajes del chat
@socketio.on('message')
def handle_message(message):
    print('Mensaje recibido: ' + message)
    color = session.get('color')
    if not color:
        color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        session['color'] = color
    send({'text': message, 'color': color}, broadcast=True)

# Manejador para cuando un usuario se conecta
@socketio.on('connect')
def handle_connect():
    # Añade al usuario a su propia sala
    join_room(request.sid)

    # Comprueba si el usuario ha iniciado sesión
    if 'email' in session:
        # Obtiene el nombre de usuario del correo electrónico
        username = session['email'].split('@')[0]

        # Envia un mensaje con fondo verde al usuario que se acaba de conectar
        emit('message', {'text': f'{username} conectado', 'color': '#008000', 'background': '#008000'}, room=request.sid)

        # Envia un mensaje con fondo azul a todos los demás usuarios
        emit('message', {'text': f'{username} conectado', 'color': '#0000FF', 'background': '#0000FF'}, broadcast=True, include_self=False)
# Iniciamos la aplicación
if __name__ == '__main__':
    create_table()
    socketio.run(app, debug=True)