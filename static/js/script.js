var socket = io.connect('http://' + document.domain + ':' + location.port);

socket.on('users', function(users) {
    // Obtiene la lista de usuarios
    var userList = document.getElementById('user-list');

    // Limpia la lista de usuarios
    while (userList.firstChild) {
        userList.removeChild(userList.firstChild);
    }

    // Añade cada usuario a la lista
    for (var i = 0; i < users.length; i++) {
        var li = document.createElement('li');
        li.textContent = users[i];
        userList.appendChild(li);
    }
});