/**
 * IPD frontend verification: the bed board must be driven by real server data
 * (no hard-coded layout), and the ward workflow must work end-to-end in the UI.
 */
const { chromium } = require('playwright');
const fs = require('fs');

const APP = 'http://localhost:3000/';
const API = 'http://127.0.0.1:8000';
const OUT = 'C:/Users/welcome/OneDrive/Documents/vs code/hospital_os/_ipd_ui';
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const check = (n, ok, extra = '') => { results.push({ n, ok, extra }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}${extra ? '  -> ' + extra : ''}`); };
const stamp = Date.now().toString().slice(-6);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1400 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  page.on('dialog', d => d.accept());

  await page.goto(APP, { waitUntil: 'networkidle' });
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'admin123');
  await page.click('button[type="submit"]');
  await page.waitForSelector('text=Welcome back', { timeout: 20000 });
  const token = await page.evaluate(() => localStorage.getItem('token'));
  const api = async (method, path, body) => {
    const r = await ctx.request.fetch(`${API}${path}`, {
      method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: body ? JSON.stringify(body) : undefined,
    });
    return { status: r.status(), body: await r.json().catch(() => null) };
  };

  const nav = async label => {
    const esc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const it = page.locator('.nav-item').filter({ hasText: new RegExp(`^\\s*${esc}\\s*$`) }).first();
    await it.dispatchEvent('click');
    await page.waitForTimeout(1000);
  };

  // ---------- Ward & Bed Setup creates the real structure via the UI ----------
  await nav('Ward & Bed Setup');
  let body = await page.textContent('body');
  check('Ward & Bed Setup screen renders', /Ward & Bed Setup/.test(body));
  check('it shows the configured capacity table', /Configured capacity/.test(body));

  const deptName = `UI Dept ${stamp}`;
  const cards = page.locator('.glass-card');
  // Department card
  const deptCard = cards.filter({ hasText: /^Department/ }).first();
  await deptCard.locator('input[type="text"]').nth(0).fill(deptName);
  await deptCard.locator('input[type="text"]').nth(1).fill(`UD${stamp}`);
  await deptCard.locator('button:has-text("Add department")').click();
  await page.waitForTimeout(1500);

  const wardName = `UI Ward ${stamp}`;
  const wardCode = `UW${stamp}`;
  const wardCard = cards.filter({ hasText: /^Ward/ }).first();
  await wardCard.locator('input[type="text"]').nth(0).fill(wardName);
  await wardCard.locator('input[type="text"]').nth(1).fill(wardCode);
  await wardCard.locator('button:has-text("Add ward")').click();
  await page.waitForTimeout(1500);

  const roomNumber = `R${stamp}`;
  const roomCard = cards.filter({ hasText: /^Room/ }).first();
  await roomCard.locator('select').selectOption({ label: wardName });
  await roomCard.locator('input[type="text"]').nth(0).fill(roomNumber);
  await roomCard.locator('button:has-text("Add room")').click();
  await page.waitForTimeout(1500);

  const bedCode = `B${stamp}`;
  const bedCard = cards.filter({ hasText: /^Bed/ }).first();
  await bedCard.locator('select').selectOption({ label: `${wardName} / ${roomNumber}` });
  await bedCard.locator('input[type="text"]').nth(0).fill(bedCode);
  await bedCard.locator('button:has-text("Add bed")').click();
  await page.waitForTimeout(1800);

  const created = await api('GET', '/ipd/bed-board');
  const newBed = created.body.find(b => b.bed_code === bedCode);
  check('bed created through the setup UI', !!newBed, newBed ? `${newBed.ward_name}/${newBed.room_number}` : 'not found');
  body = await page.textContent('body');
  check('capacity table shows the new ward', body.includes(wardName));
  await page.screenshot({ path: `${OUT}/01-setup.png`, fullPage: true });

  // ---------- Inpatient Ward: real bed board ----------
  await nav('Inpatient Ward');
  body = await page.textContent('body');
  check('Inpatient Ward renders', /Inpatient Ward/.test(body));
  check('bed board is present', /Bed board/.test(body));
  check('ward metrics render', /Occupancy/.test(body) && /Critical \(24h\)/.test(body));
  check('the new bed appears on the board', body.includes(bedCode), body.includes(bedCode) ? '' : 'bed code missing');
  // The old hard-coded layout must be gone.
  check('no hard-coded GW- beds remain', !/\bGW-\d/.test(body));
  await page.screenshot({ path: `${OUT}/02-ward.png`, fullPage: true });

  // ---------- Admit through the UI, choosing a real bed ----------
  const patient = await api('POST', '/patients/', {
    name: `UI Ward Patient ${stamp}`, age: 58, gender: 'Male', phone: `93${stamp.padStart(8, '0').slice(0, 8)}`,
  });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('text=Welcome back', { timeout: 20000 });
  await nav('Admit Patient');
  const admitCard = page.locator('.glass-card').filter({ hasText: 'Admit Patient' }).first();

  // Pick the patient in the react-select control.
  const patientInput = admitCard.locator('.form-group').filter({ hasText: 'Select Patient' }).locator('input').first();
  await patientInput.click();
  await patientInput.type(`UI Ward Patient ${stamp}`, { delay: 25 });
  await page.waitForTimeout(900);
  await page.locator('div[class*="-option"]').first().click();
  await page.waitForTimeout(400);

  await admitCard.locator('.ward-tab').filter({ hasText: wardName }).first().click();
  await page.waitForTimeout(800);
  await admitCard.locator('.bus-bed-item.available').first().click();
  await page.waitForTimeout(400);
  await admitCard.locator('button:has-text("Admit Patient")').click();
  await page.waitForTimeout(2500);

  const afterAdmit = await api('GET', '/ipd/bed-board');
  const occupied = afterAdmit.body.filter(b => b.ward_name === wardName && b.status === 'Occupied');
  check('bed allocated through the admit form', occupied.length === 1, `${occupied.length} occupied`);
  await page.screenshot({ path: `${OUT}/03-admit.png`, fullPage: true });

  // ---------- Ward record: chart, medicate, discharge ----------
  await nav('Inpatient Ward');
  await page.waitForTimeout(1000);
  const openBtn = page.locator('button:has-text("Open record")').first();
  await openBtn.dispatchEvent('click');
  await page.waitForSelector('text=Nursing chart', { timeout: 15000 });
  const rec = page.locator('.modal-content').first();
  check('ward record opens', /Nursing chart/.test(await rec.textContent()));

  // Chart vitals
  const vitalInputs = rec.locator('form input[type="number"]');
  await vitalInputs.nth(0).fill('38.4');   // temperature
  await vitalInputs.nth(1).fill('104');    // pulse
  await vitalInputs.nth(5).fill('93');     // spo2
  await rec.locator('button:has-text("Chart vitals")').click();
  await page.waitForTimeout(2000);
  check('vitals charted from the UI', /38\.4/.test(await rec.textContent()));

  // Prescribe + administer
  const medInputs = rec.locator('form').nth(1).locator('input[type="text"]');
  await medInputs.nth(0).fill('Tab. UI Medicine');
  await medInputs.nth(1).fill('500 mg');
  await rec.locator('button:has-text("Prescribe")').click();
  await page.waitForTimeout(2000);
  check('medication prescribed from the UI', /Tab\. UI Medicine/.test(await rec.textContent()));
  await rec.locator('button:has-text("Given")').first().click();
  await page.waitForTimeout(1800);
  check('administration recorded', /Given/.test(await rec.textContent()));

  // Discharge summary
  const summaryArea = rec.locator('.glass-card').filter({ hasText: 'Discharge summary' }).first();
  await summaryArea.locator('input[type="text"]').first().fill('UI test diagnosis');
  await summaryArea.locator('button:has-text("Save draft")').click();
  await page.waitForTimeout(2000);
  check('discharge summary saved', /Draft/.test(await page.textContent('.modal-content')));
  await page.screenshot({ path: `${OUT}/04-record.png`, fullPage: true });

  // Discharge
  await rec.locator('button:has-text("Discharge patient")').click();
  await page.waitForTimeout(600);
  await rec.locator('button:has-text("Confirm discharge")').click();
  await page.waitForTimeout(2200);
  const finalBoard = await api('GET', '/ipd/bed-board');
  const releasedBed = finalBoard.body.find(b => b.bed_code === bedCode);
  check('bed released to cleaning after discharge', releasedBed?.status === 'Cleaning', releasedBed?.status);
  check('admission marked discharged',
    (await api('GET', '/ip-admissions/?limit=5')).body.some(a => a.patient_id === patient.body.id && a.status === 'Discharged'));

  // ---------- Nurse role ----------
  await api('POST', '/staff/', { username: `nurse_ui${stamp}`, password: 'Staff@Pass1', role: 'Nurse' });
  const nctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
  const np = await nctx.newPage();
  await np.goto(APP, { waitUntil: 'networkidle' });
  await np.fill('input[type="text"]', `nurse_ui${stamp}`);
  await np.fill('input[type="password"]', 'Staff@Pass1');
  await np.click('button[type="submit"]');
  await np.waitForSelector('text=Welcome back', { timeout: 20000 });
  const nurseBody = await np.textContent('body');
  check('Nurse lands on the bed board', /Bed Board & Ward|Inpatient Ward/.test(nurseBody));
  check('Nurse sees ward navigation', /Bed Board/.test(nurseBody));
  await np.screenshot({ path: `${OUT}/05-nurse.png`, fullPage: true });
  await nctx.close();

  const real = errors.filter(e => !/favicon/i.test(e));
  check('no uncaught errors', real.length === 0, real.slice(0, 2).join(' | '));

  await browser.close();
  const failed = results.filter(r => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length) { console.log(JSON.stringify(failed, null, 2)); process.exit(1); }
})();
