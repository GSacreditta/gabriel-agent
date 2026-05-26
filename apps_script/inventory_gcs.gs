/**
 * GCS Writer for Gmail Inventory
 *
 * Writes inventory CSVs and stats.md to the gmail-finanzas GCS bucket.
 * Uses the Apps Script OAuth token (same Google identity) to call the GCS JSON API.
 *
 * Script Properties required:
 *   GCS_BUCKET: gmail-finanzas
 */

// ─── GCS Upload ──────────────────────────────────────────────────────

function writeToGCS(messages, attachments, senderStats, runId, startTime) {
  const bucket = PropertiesService.getScriptProperties().getProperty('GCS_BUCKET');
  if (!bucket) {
    throw new Error('GCS_BUCKET not set in Script Properties');
  }

  const prefix = 'inventory/' + runId;

  // messages.csv
  const messagesCsv = buildMessagesCsv(messages);
  uploadToGCS(bucket, prefix + '/messages.csv', messagesCsv, 'text/csv');

  // attachments.csv
  const attachmentsCsv = buildAttachmentsCsv(attachments);
  uploadToGCS(bucket, prefix + '/attachments.csv', attachmentsCsv, 'text/csv');

  // senders_summary.csv
  const sendersCsv = buildSendersCsv(senderStats);
  uploadToGCS(bucket, prefix + '/senders_summary.csv', sendersCsv, 'text/csv');

  // stats.md
  const statsMd = buildStatsMd(messages, attachments, senderStats, runId);
  uploadToGCS(bucket, prefix + '/stats.md', statsMd, 'text/markdown');

  Logger.log('   ☁️ GCS path: gs://' + bucket + '/' + prefix + '/');
}

function uploadToGCS(bucket, objectName, content, contentType) {
  const url = 'https://storage.googleapis.com/upload/storage/v1/b/'
    + encodeURIComponent(bucket)
    + '/o?uploadType=media&name='
    + encodeURIComponent(objectName);

  const options = {
    method: 'POST',
    contentType: contentType,
    payload: content,
    headers: {
      Authorization: 'Bearer ' + ScriptApp.getOAuthToken()
    },
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  const code = response.getResponseCode();

  if (code !== 200) {
    Logger.log('⚠️ GCS upload failed for ' + objectName + ': HTTP ' + code);
    Logger.log('   ' + response.getContentText().substring(0, 300));
    throw new Error('GCS upload failed: HTTP ' + code);
  }

  Logger.log('   ☁️ ' + objectName);
}

// ─── Re-run GCS upload only (if initial upload failed) ───────────────

function writeToGCSOnly() {
  Logger.log('📤 Re-uploading from Sheet to GCS...');

  const ss = SpreadsheetApp.getActiveSpreadsheet()
    || SpreadsheetApp.openById(getDriveFileByName('Gmail Inventory'));

  const messagesSheet = ss.getSheetByName('Messages');
  const attachmentsSheet = ss.getSheetByName('Attachments');

  if (!messagesSheet) throw new Error('Messages sheet not found');

  // Reconstruct data from sheet
  const messagesData = sheetToObjects(messagesSheet);
  const attachmentsData = attachmentsSheet ? sheetToObjects(attachmentsSheet) : [];

  // Build sender stats from messages
  const senderStats = {};
  messagesData.forEach(m => {
    const domain = extractDomain(m.from_email || '');
    if (!senderStats[domain]) {
      senderStats[domain] = {
        domain: domain, message_count: 0, attachment_count: 0,
        attachment_bytes: 0, first_date: m.date_iso, last_date: m.date_iso,
        sample_subjects: []
      };
    }
    const s = senderStats[domain];
    s.message_count++;
    s.attachment_count += parseInt(m.attachment_count) || 0;
    s.attachment_bytes += parseInt(m.attachment_total_bytes) || 0;
    if (m.date_iso < s.first_date) s.first_date = m.date_iso;
    if (m.date_iso > s.last_date) s.last_date = m.date_iso;
    if (s.sample_subjects.length < 3) s.sample_subjects.push((m.subject || '').substring(0, 60));
  });

  const runId = Utilities.formatDate(new Date(), 'UTC', "yyyyMMdd'T'HHmmss'Z'");
  writeToGCS(messagesData, attachmentsData, senderStats, runId, new Date());
  Logger.log('✅ GCS re-upload complete');
}

function sheetToObjects(sheet) {
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];
  const headers = data[0];
  return data.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = row[i]; });
    return obj;
  });
}

// ─── CSV Builders ────────────────────────────────────────────────────

function buildMessagesCsv(messages) {
  const headers = [
    'message_id', 'thread_id', 'date_iso', 'from_email', 'from_name',
    'to', 'subject', 'labels', 'has_attachments', 'attachment_count',
    'attachment_total_bytes', 'snippet', 'entity_guess',
    'entity_confidence', 'entity_reasoning'
  ];

  const rows = [headers.join(',')];
  messages.forEach(m => {
    rows.push(headers.map(h => csvEscape(m[h])).join(','));
  });

  return rows.join('\n');
}

function buildAttachmentsCsv(attachments) {
  const headers = ['message_id', 'filename', 'mime_type', 'size_bytes'];
  const rows = [headers.join(',')];
  attachments.forEach(a => {
    rows.push(headers.map(h => csvEscape(a[h])).join(','));
  });
  return rows.join('\n');
}

function buildSendersCsv(senderStats) {
  const headers = ['domain', 'message_count', 'attachment_count', 'attachment_bytes',
                    'first_date', 'last_date', 'sample_subjects'];
  const rows = [headers.join(',')];

  const sorted = Object.values(senderStats).sort((a, b) => b.message_count - a.message_count);
  sorted.forEach(s => {
    rows.push([
      csvEscape(s.domain), s.message_count, s.attachment_count, s.attachment_bytes,
      csvEscape(s.first_date), csvEscape(s.last_date),
      csvEscape(s.sample_subjects.join(' | '))
    ].join(','));
  });

  return rows.join('\n');
}

function buildStatsMd(messages, attachments, senderStats, runId) {
  const lines = [];
  lines.push('# Gmail Inventory Stats — Run ' + runId);
  lines.push('');
  lines.push('Generated: ' + new Date().toISOString());
  lines.push('Scope: label:' + CONFIG.LABEL_NAME);
  lines.push('Account: ' + Session.getActiveUser().getEmail());
  lines.push('');
  lines.push('## Summary');
  lines.push('');
  lines.push('- **Total messages**: ' + messages.length);
  lines.push('- **Total attachments**: ' + attachments.length);
  lines.push('- **Unique sender domains**: ' + Object.keys(senderStats).length);

  const totalBytes = messages.reduce((sum, m) => sum + (m.attachment_total_bytes || 0), 0);
  lines.push('- **Total attachment size**: ' + (totalBytes / 1024 / 1024).toFixed(1) + ' MB');
  lines.push('');

  // Top senders
  lines.push('## Top 20 Senders');
  lines.push('');
  lines.push('| Domain | Messages |');
  lines.push('|--------|----------|');
  const sorted = Object.values(senderStats).sort((a, b) => b.message_count - a.message_count);
  sorted.slice(0, 20).forEach(s => {
    lines.push('| ' + s.domain + ' | ' + s.message_count + ' |');
  });
  lines.push('');

  // MIME type breakdown
  const mimeCounts = {};
  attachments.forEach(a => {
    const mt = a.mime_type || 'unknown';
    mimeCounts[mt] = (mimeCounts[mt] || 0) + 1;
  });
  lines.push('## Attachment MIME Types');
  lines.push('');
  lines.push('| MIME Type | Count |');
  lines.push('|----------|-------|');
  Object.entries(mimeCounts).sort((a, b) => b[1] - a[1]).forEach(([mt, c]) => {
    lines.push('| ' + mt + ' | ' + c + ' |');
  });

  return lines.join('\n');
}

function csvEscape(value) {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (str.indexOf(',') !== -1 || str.indexOf('"') !== -1 || str.indexOf('\n') !== -1) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}
