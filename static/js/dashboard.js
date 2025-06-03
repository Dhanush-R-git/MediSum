/**
 * Handles:
 *  - Sidebar icon “active” highlighting
 *  - Patient row clicking (redirect)
 *  - Patient search filtering
 *  - Collapse/expand right panel (optional)
 *  - Any other global UI behavior
 */

document.addEventListener('DOMContentLoaded', () => {
  // === Sidebar tab “active” state ===
  const sidebarIcons = document.querySelectorAll('.sidebar-icon');
  sidebarIcons.forEach(icon => {
    icon.addEventListener('click', () => {
      sidebarIcons.forEach(ic => ic.classList.remove('active'));
      icon.classList.add('active');
      // Optionally, scroll to the appropriate tab or highlight
      const target = icon.getAttribute('data-target');
      // If using AJAX to switch main content, do it here.
    });
  });

  // === Right panel collapse/expand ===
  const toggleBtn = document.getElementById('toggle_patient_list');
  const patientList = document.getElementById('patient_list');
  if (toggleBtn && patientList) {
    toggleBtn.addEventListener('click', () => {
      if (patientList.classList.contains('hidden')) {
        patientList.classList.remove('hidden');
      } else {
        patientList.classList.add('hidden');
      }
    });
  }

  // === Patient search (duplicate logic from inline script if needed) ===
  const patientSearch = document.getElementById('patient_search');
  if (patientSearch) {
    patientSearch.addEventListener('input', () => {
      const term = patientSearch.value.toLowerCase();
      const rows = document.querySelectorAll('#patient_list .patient-row');
      rows.forEach(row => {
        const text = row.innerText.toLowerCase();
        if (text.includes(term)) {
          row.classList.remove('hidden');
        } else {
          row.classList.add('hidden');
        }
      });
    });
  }

  // === Patient row click redirection (duplicate if needed) ===
  const rows = document.querySelectorAll('#patient_list .patient-row');
  rows.forEach(row => {
    row.addEventListener('click', () => {
      const pid = row.getAttribute('data-pid');
      if (pid) {
        window.location.href = `/dashboard/${pid}`;
      }
    });
  });
});
