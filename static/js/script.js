document.addEventListener('DOMContentLoaded', function () {
  // 1. Delete confirmation for any form marked .confirm-delete
  document.querySelectorAll('form.confirm-delete').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var msg = form.getAttribute('data-message') || 'Are you sure you want to delete this item?';
      if (!window.confirm(msg)) { e.preventDefault(); }
    });
  });

  // 2. Bootstrap form validation + password confirmation
  document.querySelectorAll('form.needs-validation').forEach(function (form) {
    var pw = form.querySelector('#password');
    var cpw = form.querySelector('#confirm_password');
    function checkMatch() {
      if (pw && cpw) {
        cpw.setCustomValidity(cpw.value && pw.value !== cpw.value ? 'Passwords do not match' : '');
      }
    }
    if (pw && cpw) {
      pw.addEventListener('input', checkMatch);
      cpw.addEventListener('input', checkMatch);
    }
    form.addEventListener('submit', function (e) {
      checkMatch();
      if (!form.checkValidity()) { e.preventDefault(); e.stopPropagation(); }
      form.classList.add('was-validated');
    });
  });

  // 3. Auto-hide alerts after 5 seconds
  document.querySelectorAll('.alert.auto-hide').forEach(function (alertEl) {
    setTimeout(function () {
      alertEl.classList.remove('show');
      setTimeout(function () { alertEl.remove(); }, 400);
    }, 5000);
  });

  // 4. Service details + price display on the booking form
  var serviceSelect = document.getElementById('service_id');
  var info = document.getElementById('serviceInfo');
  function showService() {
    if (!serviceSelect || !info) return;
    var opt = serviceSelect.options[serviceSelect.selectedIndex];
    if (!opt || !opt.value) { info.classList.add('d-none'); return; }
    document.getElementById('svcDesc').textContent = opt.dataset.description;
    document.getElementById('svcPrice').textContent = '\u20B9' + opt.dataset.price;
    var d = parseInt(opt.dataset.days, 10);
    document.getElementById('svcDays').textContent = d + (d === 1 ? ' day' : ' days');
    info.classList.remove('d-none');
  }
  if (serviceSelect) { serviceSelect.addEventListener('change', showService); showService(); }

  // 5. Booking / pickup status dropdowns: colour the border by current choice
  document.querySelectorAll('select.status-select').forEach(function (sel) {
    function paint() {
      sel.className = sel.className.replace(/\bs-[a-z-]+\b/g, '').trim();
      sel.classList.add('s-' + sel.value.toLowerCase().replace(/ /g, '-'));
    }
    sel.addEventListener('change', paint);
    paint();
  });
});
