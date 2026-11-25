/* Mans&Co Magazine — interactions légères (menu, like) */
(function () {
    'use strict';

    var navToggle = document.getElementById('nav-toggle');
    var nav = document.getElementById('main-nav');
    if (navToggle && nav) {
        navToggle.addEventListener('click', function () {
            var open = nav.classList.toggle('open');
            navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    document.querySelectorAll('.dropdown .drop-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            if (window.innerWidth <= 760) {
                btn.parentElement.classList.toggle('open');
            }
        });
    });

    document.querySelectorAll('.like-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var slug = window.location.pathname.split('/').pop();
            fetch('/article/' + encodeURIComponent(slug) + '/like', {
                method: 'POST',
                headers: { 'X-Requested-With': 'fetch' }
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    var count = btn.querySelector('.like-count');
                    var icon = btn.querySelector('i');
                    if (count) count.textContent = data.likes;
                    btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
                    btn.classList.toggle('btn-gold', data.liked);
                    btn.classList.toggle('btn-outline', !data.liked);
                    if (icon) {
                        icon.classList.toggle('fa-solid', data.liked);
                        icon.classList.toggle('fa-regular', !data.liked);
                    }
                })
                .catch(function () { window.location.reload(); });
        });
    });
})();
