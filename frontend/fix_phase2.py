
# Add Print CSS
with open('f:\\\\Hospital Soft\\\\frontend\\\\src\\\\App.css', 'a', encoding='utf-8') as f:
    f.write('''\n\n@media print {
  .no-print, .sidebar, .header, .nav-item {
    display: none !important;
  }
  body, .app-container {
    background: white;
    color: black;
    margin: 0;
    padding: 0;
  }
  .glass-card {
    border: none;
    box-shadow: none;
    background: white;
    color: black;
  }
  .print-section {
    width: 100%;
    margin: 0;
    padding: 0;
  }
}\n''')
print('Added Print CSS')

