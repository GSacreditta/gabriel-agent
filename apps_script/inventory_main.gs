/**
 * Gmail Inventory Pass — Finanzas Label Only
 *
 * Google Apps Script that enumerates all emails under the "Finanzas" Gmail label,
 * extracts metadata + attachment info, and writes to:
 *   1. A Google Sheet (for review)
 *   2. GCS bucket gmail-finanzas (for the pipeline)
 *
 * Runs under sternbergg@gmail.com — not blocked by Advanced Protection
 * because Apps Script is a Google first-party service.
 *
 * SETUP:
 *   1. Go to script.google.com → New Project
 *   2. Paste this entire file into Code.gs
 *   3. Paste inventory_gcs.gs into a second file (File → New → Script)
 *   4. In Project Settings → Script Properties, add:
 *      - GCS_BUCKET: gmail-finanzas
 *      - GCP_PROJECT: location-19291
 *   5. In Services (left sidebar), add "Gmail API" (Advanced Gmail Service)
 *   6. Run runInventory() — authorize when prompted
 */

// ─── Configuration ─────────────────────────────────────────────────────

const CONFIG = {
  LABEL_NAME: 'Finanzas',
  SHEET_NAME: 'Gmail Inventory',
  BATCH_SIZE: 100,        // Messages per Gmail API page
  MAX_MESSAGES: 2000,     // Safety cap
};

// ─── Main Entry Point ──────────────────────────────────────────────────

function runInventory() {
  const startTime = new Date();
  Logger.log('🚀 Starting Gmail Inventory Pass');
  Logger.log('   Scope: label:' + CONFIG.LABEL_NAME);
  Logger.log('   Account: ' + Session.getActiveUser().getEmail());

  // Get or create spreadsheet
  const ss = getOrCreateSpreadsheet();

  // Set up sheets
  const messagesSheet = getOrCreateSheet(ss, 'Messages');
  const attachmentsSheet = getOrCreateSheet(ss, 'Attachments');
  const sendersSheet = getOrCreateSheet(ss, 'Senders Summary');
  const statsSheet = getOrCreateSheet(ss, 'Stats');

  // Write headers
  writeMessagesHeaders(messagesSheet);
  writeAttachmentsHeaders(attachmentsSheet);

  // Find the Finanzas label
  const label = GmailApp.getUserLabelByName(CONFIG.LABEL_NAME);
  if (!label) {
    Logger.log('❌ Label "' + CONFIG.LABEL_NAME + '" not found!');
    Logger.log('   Available labels: ' + GmailApp.getUserLabels().map(l => l.getName()).join(', '));
    throw new Error('Label "' + CONFIG.LABEL_NAME + '" not found in Gmail');
  }

  Logger.log('✅ Found label: ' + CONFIG.LABEL_NAME);

  // Enumerate all threads under the label
  const allMessages = [];
  const allAttachments = [];
  const senderStats = {};
  let threadCount = 0;
  let start = 0;

  while (start < CONFIG.MAX_MESSAGES) {
    const threads = label.getThreads(start, CONFIG.BATCH_SIZE);
    if (threads.length === 0) break;

    for (const thread of threads) {
      threadCount++;
      const messages = thread.getMessages();

      for (const message of messages) {
        const msgData = extractMessageMetadata(message, thread);
        allMessages.push(msgData);

        // Track sender stats
        const domain = extractDomain(msgData.from_email);
        if (!senderStats[domain]) {
          senderStats[domain] = {
            domain: domain,
            message_count: 0,
            attachment_count: 0,
            attachment_bytes: 0,
            first_date: msgData.date_iso,
            last_date: msgData.date_iso,
            sample_subjects: []
          };
        }
        const stats = senderStats[domain];
        stats.message_count++;
        stats.attachment_count += msgData.attachment_count;
        stats.attachment_bytes += msgData.attachment_total_bytes;
        if (msgData.date_iso < stats.first_date) stats.first_date = msgData.date_iso;
        if (msgData.date_iso > stats.last_date) stats.last_date = msgData.date_iso;
        if (stats.sample_subjects.length < 3) {
          stats.sample_subjects.push(msgData.subject.substring(0, 60));
        }

        // Extract attachment metadata
        const attachments = message.getAttachments();
        for (const att of attachments) {
          allAttachments.push({
            message_id: msgData.message_id,
            filename: att.getName(),
            mime_type: att.getContentType(),
            size_bytes: att.getSize()
          });
        }
      }

      // Progress logging every 50 threads
      if (threadCount % 50 === 0) {
        Logger.log('   Processed ' + threadCount + ' threads, ' + allMessages.length + ' messages...');
      }
    }

    start += threads.length;
    if (threads.length < CONFIG.BATCH_SIZE) break;
  }

  Logger.log('📊 Enumeration complete:');
  Logger.log('   Threads: ' + threadCount);
  Logger.log('   Messages: ' + allMessages.length);
  Logger.log('   Attachments: ' + allAttachments.length);
  Logger.log('   Unique senders: ' + Object.keys(senderStats).length);

  // ── Write to Google Sheet ──
  Logger.log('📝 Writing to Google Sheet...');
  writeMessagesData(messagesSheet, allMessages);
  writeAttachmentsData(attachmentsSheet, allAttachments);
  writeSendersSummary(sendersSheet, senderStats);
  writeStats(statsSheet, allMessages, allAttachments, senderStats, startTime);

  // ── Write to GCS ──
  Logger.log('☁️ Writing to GCS...');
  try {
    const runId = Utilities.formatDate(startTime, 'UTC', "yyyyMMdd'T'HHmmss'Z'");
    writeToGCS(allMessages, allAttachments, senderStats, runId, startTime);
    Logger.log('✅ GCS upload complete');
  } catch (e) {
    Logger.log('⚠️ GCS upload failed (Sheet data is safe): ' + e.message);
    Logger.log('   You can export from the Sheet manually or fix GCS config and re-run writeToGCSOnly()');
  }

  const elapsed = ((new Date() - startTime) / 1000).toFixed(1);
  Logger.log('');
  Logger.log('✅ Inventory pass complete in ' + elapsed + 's');
  Logger.log('   Sheet: ' + ss.getUrl());
  Logger.log('   Messages: ' + allMessages.length);
  Logger.log('   Attachments: ' + allAttachments.length);

  return {
    spreadsheet_url: ss.getUrl(),
    total_messages: allMessages.length,
    total_attachments: allAttachments.length,
    unique_senders: Object.keys(senderStats).length,
    elapsed_seconds: parseFloat(elapsed)
  };
}

// ─── Message Metadata Extraction ─────────────────────────────────────

function extractMessageMetadata(message, thread) {
  const from_raw = message.getFrom();
  const parsed = parseSender(from_raw);

  const attachments = message.getAttachments();
  const totalBytes = attachments.reduce((sum, att) => sum + att.getSize(), 0);

  return {
    message_id: message.getId(),
    thread_id: thread.getId(),
    date_iso: message.getDate().toISOString(),
    from_email: parsed.email,
    from_name: parsed.name,
    to: message.getTo(),
    subject: message.getSubject() || '',
    labels: thread.getLabels().map(l => l.getName()).join(','),
    has_attachments: attachments.length > 0,
    attachment_count: attachments.length,
    attachment_total_bytes: totalBytes,
    snippet: message.getPlainBody() ? message.getPlainBody().substring(0, 200) : '',
    // Entity fields (populated later by LLM pass)
    entity_guess: '',
    entity_confidence: '',
    entity_reasoning: ''
  };
}

// ─── Sheet Writers ───────────────────────────────────────────────────

function getOrCreateSpreadsheet() {
  // Look for existing spreadsheet
  const files = DriveApp.getFilesByName(CONFIG.SHEET_NAME);
  if (files.hasNext()) {
    const file = files.next();
    Logger.log('📄 Using existing spreadsheet: ' + file.getUrl());
    return SpreadsheetApp.open(file);
  }

  // Create new
  const ss = SpreadsheetApp.create(CONFIG.SHEET_NAME);
  Logger.log('📄 Created spreadsheet: ' + ss.getUrl());
  return ss;
}

function getOrCreateSheet(ss, name) {
  let sheet = ss.getSheetByName(name);
  if (sheet) {
    sheet.clear();
  } else {
    sheet = ss.insertSheet(name);
  }
  return sheet;
}

function writeMessagesHeaders(sheet) {
  const headers = [
    'message_id', 'thread_id', 'date_iso', 'from_email', 'from_name',
    'to', 'subject', 'labels', 'has_attachments', 'attachment_count',
    'attachment_total_bytes', 'snippet', 'entity_guess',
    'entity_confidence', 'entity_reasoning'
  ];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  sheet.setFrozenRows(1);
}

function writeAttachmentsHeaders(sheet) {
  const headers = ['message_id', 'filename', 'mime_type', 'size_bytes'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  sheet.setFrozenRows(1);
}

function writeMessagesData(sheet, messages) {
  if (messages.length === 0) return;

  const rows = messages.map(m => [
    m.message_id, m.thread_id, m.date_iso, m.from_email, m.from_name,
    m.to, m.subject, m.labels, m.has_attachments, m.attachment_count,
    m.attachment_total_bytes, m.snippet, m.entity_guess,
    m.entity_confidence, m.entity_reasoning
  ]);

  sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  Logger.log('   Messages sheet: ' + rows.length + ' rows');
}

function writeAttachmentsData(sheet, attachments) {
  if (attachments.length === 0) return;

  const rows = attachments.map(a => [
    a.message_id, a.filename, a.mime_type, a.size_bytes
  ]);

  sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  Logger.log('   Attachments sheet: ' + rows.length + ' rows');
}

function writeSendersSummary(sheet, senderStats) {
  const headers = ['domain', 'message_count', 'attachment_count', 'attachment_bytes',
                    'first_date', 'last_date', 'sample_subjects'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  sheet.setFrozenRows(1);

  const sorted = Object.values(senderStats).sort((a, b) => b.message_count - a.message_count);
  if (sorted.length === 0) return;

  const rows = sorted.map(s => [
    s.domain, s.message_count, s.attachment_count, s.attachment_bytes,
    s.first_date, s.last_date, s.sample_subjects.join(' | ')
  ]);

  sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  Logger.log('   Senders summary: ' + rows.length + ' domains');
}

function writeStats(sheet, messages, attachments, senderStats, startTime) {
  const lines = [];
  lines.push(['Gmail Inventory Stats']);
  lines.push(['Generated', new Date().toISOString()]);
  lines.push(['Scope', 'label:' + CONFIG.LABEL_NAME]);
  lines.push(['Account', Session.getActiveUser().getEmail()]);
  lines.push(['']);
  lines.push(['Total messages', messages.length]);
  lines.push(['Total attachments', attachments.length]);
  lines.push(['Unique sender domains', Object.keys(senderStats).length]);

  const totalBytes = messages.reduce((sum, m) => sum + m.attachment_total_bytes, 0);
  lines.push(['Total attachment size (MB)', (totalBytes / 1024 / 1024).toFixed(1)]);

  const withAtt = messages.filter(m => m.attachment_count > 0).length;
  lines.push(['Messages with attachments', withAtt]);
  lines.push(['Messages without attachments', messages.length - withAtt]);
  lines.push(['']);
  lines.push(['Top 10 Sender Domains', 'Count']);

  const sorted = Object.values(senderStats).sort((a, b) => b.message_count - a.message_count);
  sorted.slice(0, 10).forEach(s => {
    lines.push([s.domain, s.message_count]);
  });

  // Pad rows to 2 columns
  const rows = lines.map(l => l.length === 1 ? [l[0], ''] : l);
  sheet.getRange(1, 1, rows.length, 2).setValues(rows);
}

// ─── Utilities ───────────────────────────────────────────────────────

function parseSender(from_raw) {
  const match = from_raw.match(/^"?([^"<]*)"?\s*<?([^>]*)>?$/);
  if (match) {
    return { name: match[1].trim(), email: match[2].trim() };
  }
  return { name: '', email: from_raw.trim() };
}

function extractDomain(email) {
  if (email.indexOf('@') !== -1) {
    return email.split('@')[1].toLowerCase().trim();
  }
  return 'unknown';
}
