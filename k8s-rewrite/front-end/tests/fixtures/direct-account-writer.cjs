'use strict';
// Independent public SQLite fixture owner; never emit rows, subjects or error text.
const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync(process.argv[2], { timeout: 0 });
process.on('message', message => {
  try {
    if (message?.operation === 'lock') { db.exec('BEGIN EXCLUSIVE'); process.send({ event: 'locked' }); }
    else if (message?.operation === 'release') { db.exec('ROLLBACK'); process.send({ event: 'released' }); }
    else if (message?.operation === 'reset') {
      db.prepare('UPDATE users SET sessionVersion=sessionVersion+1 WHERE id=?').run(message.subject);
      process.send({ event: 'reset' });
    } else if (message?.operation === 'close') { db.close(); process.disconnect(); }
    else throw Error('PUBLIC_FIXTURE_REFUSED');
  } catch (error) { process.send({ event: 'refused', code: Number.isInteger(error.errcode) ? error.errcode : 0 }); }
});
process.send({ event: 'ready' });
