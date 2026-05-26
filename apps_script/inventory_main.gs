/**
 * Gmail Inventory Pass — Finanzas Label Only
 *
 * Google Apps Script that enumerates all emails under the "Finanzas" Gmail label,
 * extracts metadata + attachment info, and writes to:
 *   1. A Google Sheet (for review)
 *   2. GCS bucket gmail-finanzas (for the pipeline)
 *
 * SECURITY:
 *   - Uses the Gmail Advanced Service with gmail.readonly scope ONLY
 *   - Cannot modify, delete, send, or forward any email
 *   - No data sent to external APIs — only your Sheet and your GCS bucket
 *   - Script code is fully auditable
 *
 * SETUP:
 *   1. Go to script.google.com → New Project (signed in as sternbergg@gmail.com)
 *   2. Paste this entire file into Code.gs
 *   3. Paste inventory_gcs.gs into a second file (File → New → Script)
 *   4. In Project Settings → Script Properties, add:
 *      - GCS_BUCKET: gmail-finanzas
 *   5. In Services (left sidebar, + icon), add "Gmail API" v1
 *   6. In Project Settings, check "Show appsscript.json manifest file in editor"
 *   7. Edit appsscript.json — replace oauthScopes with:
 *      "oauthScopes": [
 *        "https://www.googleapis.com/auth/gmail.readonly",
 *        "https://www.googleapis.com/auth/spreadsheets",
 *        "https://www.googleapis.com/auth/drive",
 *        "https://www.googleapis.com/auth/devstorage.read_write"
 *      ]
 *   8. Run runInventory() — authorize when prompted
 *      (Prompt should say "View your email" — NOT "manage your email")
 *
 * @OnlyCurrentDoc
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
  Logger.log('   Security: gmail.readonly scope only');

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

  // ── Find the Finanzas label via Advanced Gmail Service ──
  // (Uses gmail.readonly — no write access to Gmail)
  const labelsResponse = Gmail.Users.Labels.list('me');
  const finanzasLabel = labelsResponse.labels.find(l => l.name === CONFIG.LABEL_NAME);

  if (!finanzasLabel) {
    const allNames = labelsResponse.labels.map(l => l.name).join(', ');
    Logger.log('❌ Label "' + CONFIG.LABEL_NAME + '" not found!');
    Logger.log('   Available labels: ' + allNames);
    throw new Error('Label "' + CONFIG.LABEL_NAME + '" not found in Gmail');
  }

  Logger.log('✅ Found label: ' + finanzasLabel.name + ' (id: ' + finanzasLabel.id + ')');

  // ── Enumerate all messages under the label ──
  const allMessages = [];
  const allAttachments = [];
  const senderStats = {};
  let pageToken = null;
  let pageCount = 0;

  do {
    const listParams = {
      labelIds: [finanzasLabel.id],
      maxResults: CONFIG.BATCH_SIZE
    };
    if (pageToken) listParams.pageToken = pageToken;

    const listResponse = Gmail.Users.Messages.list('me', listParams);
    const messageStubs = listResponse.messages || [];
    pageToken = listResponse.nextPageToken || null;
    pageCount++;

    Logger.log('   Page ' + pageCount + ': ' + messageStubs.length + ' messages');

    for (const stub of messageStubs) {
      if (allMessages.length >= CONFIG.MAX_MESSAGES) {
        Logger.log('⚠️ Hit MAX_MESSAGES cap: ' + CONFIG.MAX_MESSAGES);
        pageToken = null;
        break;
      }

      // Fetch full message metadata (gmail.readonly)
      const msg = Gmail.Users.Messages.get('me', stub.id, { format: 'metadata', metadataHeaders: ['From', 'To', 'Subject', 'Date'] });
      const fullMsg = Gmail.Users.Messages.get('me', stub.id, { format: 'full' });

      const msgData = extractMessageMetadata(msg, fullMsg);
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
      if (msgData.date_iso && msgData.date_iso < stats.first_date) stats.first_date = msgData.date_iso;
      if (msgData.date_iso && msgData.date_iso > stats.last_date) stats.last_date = msgData.date_iso;
      if (stats.sample_subjects.length < 3) {
        stats.sample_subjects.push(msgData.subject.substring(0, 60));
      }

      // Extract attachment metadata from payload parts
      const attachments = extractAttachmentMetadata(fullMsg);
      for (const att of attachments) {
        allAttachments.push({
          message_id: msgData.message_id,
          filename: att.filename,
          mime_type: att.mime_type,
          size_bytes: att.size_bytes
        });
      }
    }
  } while (pageToken);

  Logger.log('📊 Enumeration complete:');
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

// ─── Message Metadata Extraction (Advanced Gmail Service) ────────────

function extractMessageMetadata(metadataMsg, fullMsg) {
  const headers = {};
  (metadataMsg.payload.headers || []).forEach(h => {
    headers[h.name] = h.value;
  });

  const from_raw = headers['From'] || '';
  const parsed = parseSender(from_raw);

  // Count attachments from full message payload
  const attachments = extractAttachmentMetadata(fullMsg);
  const totalBytes = attachments.reduce((sum, a) => sum + a.size_bytes, 0);

  // Convert epoch ms to ISO
  const dateMs = parseInt(metadataMsg.internalDate);
  const dateIso = dateMs ? new Date(dateMs).toISOString() : (headers['Date'] || '');

  return {
    message_id: metadataMsg.id,
    thread_id: metadataMsg.threadId,
    date_iso: dateIso,
    from_email: parsed.email,
    from_name: parsed.name,
    to: headers['To'] || '',
    subject: headers['Subject'] || '',
    labels: (metadataMsg.labelIds || []).join(','),
    has_attachments: attachments.length > 0,
    attachment_count: attachments.length,
    attachment_total_bytes: totalBytes,
    snippet: metadataMsg.snippet || '',
    // Entity fields (populated later by LLM pass)
    entity_guess: '',
    entity_confidence: '',
    entity_reasoning: ''
  };
}

function extractAttachmentMetadata(fullMsg) {
  const attachments = [];

  function scanParts(parts) {
    if (!parts) return;
    for (const part of parts) {
      if (part.filename && part.filename.length > 0) {
        attachments.push({
          filename: part.filename,
          mime_type: part.mimeType || 'application/octet-stream',
          size_bytes: (part.body && part.body.size) ? part.body.size : 0
        });
      }
      if (part.parts) scanParts(part.parts);
    }
  }

  if (fullMsg.payload) {
    if (fullMsg.payload.filename && fullMsg.payload.filename.length > 0) {
      attachments.push({
        filename: fullMsg.payload.filename,
        mime_type: fullMsg.payload.mimeType || 'application/octet-stream',
        size_bytes: (fullMsg.payload.body && fullMsg.payload.body.size) ? fullMsg.payload.body.size : 0
      });
    }
    scanParts(fullMsg.payload.parts);
  }

  return attachments;
}

// ─── Sheet Writers ───────────────────────────────────────────────────

function getOrCreateSpreadsheet() {
  const files = DriveApp.getFilesByName(CONFIG.SHEET_NAME);
  if (files.hasNext()) {
    const file = files.next();
    Logger.log('📄 Using existing spreadsheet: ' + file.getUrl());
    return SpreadsheetApp.open(file);
  }
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
  lines.push(['Security', 'gmail.readonly scope only']);
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
