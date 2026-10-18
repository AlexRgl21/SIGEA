/* SIGEA - comportamiento global del layout: */
(function () {
    'use strict';

    function tokenCsrf() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    /* SESIÓN POR INACTIVIDAD */
    function iniciarSesion() {
        var d = document.body.dataset;
        if (!d.sesionTotal) { return; }                      // no hay sesión iniciada

        var TOTAL = parseInt(d.sesionTotal, 10) * 1000;
        var AVISO = parseInt(d.sesionAviso, 10) * 1000;
        var PING = parseInt(d.sesionPing, 10) * 1000;
        var URL_EXTENDER = d.urlExtender;

        var temporizador = null;
        var avisoVisible = false;
        var ultimoPing = Date.now();          // la carga de la página ya renovó la cookie
        var ultimaActividad = 0;
        var pingEnCurso = false;

        function cerrarSesion(motivo) {
            var campoMotivo = document.getElementById('logout-motivo');
            if (campoMotivo) { campoMotivo.value = motivo || ''; }
            document.getElementById('form-logout').submit();
        }

        function extender() {
            return fetch(URL_EXTENDER, {
                method: 'POST',
                headers: { 'X-CSRFToken': tokenCsrf() },
                credentials: 'same-origin',
                redirect: 'manual'
            }).then(function (r) { return r.status === 204; })
              .catch(function () { return false; });
        }

        function programarAviso() {
            clearTimeout(temporizador);
            temporizador = setTimeout(mostrarAviso, TOTAL - AVISO);
        }

        function alActividad() {
            if (avisoVisible) { return; }
            var ahora = Date.now();
            if (ahora - ultimaActividad < 1000) { return; }  // no recalcular en cada mousemove
            ultimaActividad = ahora;
            programarAviso();

            if (ahora - ultimoPing > PING && !pingEnCurso) {
                pingEnCurso = true;
                extender().then(function (ok) {
                    if (ok) { ultimoPing = Date.now(); }
                    pingEnCurso = false;
                });
            }
        }

        function mostrarAviso() {
            avisoVisible = true;

            // Sin SweetAlert (CDN caído): se cierra la sesión al terminar el tiempo
            if (typeof Swal === 'undefined') {
                setTimeout(function () { cerrarSesion('inactividad'); }, AVISO);
                return;
            }

            var intervalo = null;
            Swal.fire({
                title: 'Tu sesión está por expirar',
                html: 'Por seguridad se cerrará por inactividad en ' +
                      '<b id="sigea-cuenta"></b> segundos.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Seguir conectado',
                cancelButtonText: 'Cerrar sesión',
                confirmButtonColor: '#00AEEF',
                allowOutsideClick: false,
                allowEscapeKey: false,
                timer: AVISO,
                timerProgressBar: true,
                didOpen: function () {
                    var cuenta = Swal.getHtmlContainer().querySelector('#sigea-cuenta');
                    var pintar = function () {
                        cuenta.textContent = Math.max(0, Math.ceil(Swal.getTimerLeft() / 1000));
                    };
                    pintar();
                    intervalo = setInterval(pintar, 250);
                },
                willClose: function () { clearInterval(intervalo); }
            }).then(function (resultado) {
                if (resultado.isConfirmed) {
                    extender().then(function (ok) {
                        if (ok) {
                            ultimoPing = Date.now();
                            avisoVisible = false;
                            programarAviso();
                        } else {
                            cerrarSesion('inactividad');       // la sesión ya había caducado
                        }
                    });
                    return;
                }
                var porTiempo = resultado.dismiss === Swal.DismissReason.timer;
                cerrarSesion(porTiempo ? 'inactividad' : '');
            });
        }

        ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(function (evento) {
            window.addEventListener(evento, alActividad, { passive: true });
        });
        programarAviso();
    }

    /* CAMPANA DE NOTIFICACIONES */
    function iniciarCampana() {
        var campana = document.getElementById('btn-campana');
        var panel = document.getElementById('dropdown-notis');
        if (!campana || !panel) { return; }

        var sinLeer = parseInt(campana.dataset.sinLeer, 10) || 0;
        var urlLeer = campana.dataset.urlLeer;

        function marcarLeidas() {
            if (sinLeer === 0) { return; }
            fetch(urlLeer, {
                method: 'POST',
                headers: { 'X-CSRFToken': tokenCsrf() },
                credentials: 'same-origin'
            }).then(function (r) {
                if (!r.ok) { throw new Error('HTTP ' + r.status); }
                sinLeer = 0;
                var badge = campana.querySelector('.badge-numero');
                if (badge) { badge.remove(); }
            }).catch(function (error) {
                console.warn('No se pudieron marcar las notificaciones como leídas', error);
            });
        }

        campana.addEventListener('click', function (e) {
            var abierto = panel.style.display === 'block';
            panel.style.display = abierto ? 'none' : 'block';
            if (!abierto) { marcarLeidas(); }
            e.stopPropagation();
        });

        document.addEventListener('click', function (e) {
            if (!campana.contains(e.target)) { panel.style.display = 'none'; }
        });
    }

    iniciarSesion();
    iniciarCampana();
})();