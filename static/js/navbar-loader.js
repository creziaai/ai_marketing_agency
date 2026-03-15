// navbar-loader.js
fetch('navbar.html')
  .then(res => res.text())
  .then(html => {
    document.getElementById('navbar').innerHTML = html;

    // Wait a bit for the DOM to update
    setTimeout(() => {
      const currentPage = window.location.pathname.split('/').pop() || 'index.html';
      document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPage) {
          link.style.color = '#4f46e5';
          link.style.fontWeight = 'bold';
        }
      });
    }, 50);
  });
