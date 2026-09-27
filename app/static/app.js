const $ = id => document.getElementById(id);
let token = '', conversation = '', busy = false;
function notice(text) { $('notice').textContent = text; }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...options.headers, Authorization: `Bearer ${token}`}});
  if (!response.ok) throw new Error(`요청 실패 (${response.status})`);
  return response;
}
async function json(path, body) {
  return (await api(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})).json();
}
function message(role, text, sources = []) {
  const article = document.createElement('article'); article.className = `message ${role}`;
  const heading = document.createElement('h2'); heading.textContent = role === 'user' ? '나' : '응답';
  const content = document.createElement('div'); content.textContent = text;
  article.append(heading, content); $('messages').append(article);
  if (sources.length) showSources(article, sources);
  return {article, content};
}
function showSources(article, sources) {
  const details = document.createElement('details'); details.className = 'sources';
  const summary = document.createElement('summary'); summary.textContent = `출처 ${sources.length}개`; details.append(summary);
  sources.forEach((source, i) => {
    const p = document.createElement('p');
    p.textContent = `[${i+1}] ${source.title} · ${source.version || '대화 첨부'}\n${source.text}`;
    details.append(p);
  }); article.append(details);
}
async function listConversations() {
  $('conversations').replaceChildren();
  for (const item of await json('/api/conversations')) {
    const button = document.createElement('button'); button.textContent = new Date(item.created_at).toLocaleString();
    button.onclick = async () => { if (busy) return; try {
      conversation = item.id; $('messages').replaceChildren();
      for (const row of await json(`/api/conversations/${conversation}`)) message(row.role, row.content, row.sources);
    } catch (error) { notice(error.message); } };
    $('conversations').append(button);
  }
}
async function listDocuments() {
  $('documents').replaceChildren();
  for (const doc of await json('/api/documents')) {
    const item = document.createElement('div'); item.className = 'document';
    item.textContent = `${doc.title} · ${doc.acl} · ${doc.approved ? '색인 완료' : '승인 대기'}`;
    {
      const button = document.createElement('button'); button.textContent = doc.approved ? '다시 색인' : '승인 및 색인';
      button.onclick = async () => { button.disabled = true; try { await json(`/api/documents/${doc.id}/approve`, {}); await listDocuments(); notice('승인·색인 완료'); } catch(error) { notice(error.message); button.disabled = false; } };
      item.append(button);
    } $('documents').append(item);
  }
}
$('login').onsubmit = async event => {
  event.preventDefault(); if (busy) return;
  token = $('token').value; $('token').value = ''; conversation = ''; $('messages').replaceChildren();
  try {
    const me = await json('/api/me'); $('identity').textContent = `${me.role} 연결됨`;
    $('mode-status').textContent = me.generation === 'model' ? '사용자 설정 모델 · 실제 스트리밍 추론' : 'CPU 근거 확인 데모 · LLM 추론 아님 · 해시 기반 검색';
    $('ingestion').hidden = me.role !== 'admin'; $('new-chat').disabled = false; $('send').disabled = false;
    await listConversations(); if (me.role === 'admin') await listDocuments(); notice('연결되었습니다.');
  } catch(error) { token = ''; $('send').disabled = true; $('new-chat').disabled = true; $('ingestion').hidden = true; notice(error.message); }
};
$('new-chat').onclick = async () => { if(busy) return; try { conversation = (await json('/api/conversations', {})).id; $('messages').replaceChildren(); await listConversations(); } catch(error) { notice(error.message); } };
$('upload').onsubmit = async event => {
  event.preventDefault(); const data = new FormData(); data.append('file', $('document').files[0]); data.append('acl', $('acl').value);
  try { await api('/api/documents', {method:'POST',body:data}); await listDocuments(); notice('반입 완료. 승인 버튼을 눌러야 검색됩니다.'); } catch(error) { notice(error.message); }
};
$('chat').onsubmit = async event => {
  event.preventDefault(); if(busy || !token) return; busy = true; $('send').disabled = true;
  try {
    if(!conversation) conversation = (await json('/api/conversations', {})).id;
    const file = $('attachment').files[0];
    if(file) { const data = new FormData(); data.append('file', file); await api(`/api/conversations/${conversation}/attachments`, {method:'POST',body:data}); $('attachment').value = ''; }
    const question = $('question').value; message('user', question); $('question').value = '';
    const output = message('assistant', '');
    const response = await api('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({conversation_id:conversation,question,mode:$('mode').value})});
    const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', done = false;
    while(true) {
      const packet = await reader.read(); if(packet.done) break;
      buffer += decoder.decode(packet.value,{stream:true}); let end;
      while((end=buffer.indexOf('\n\n')) >= 0) {
        const line = buffer.slice(0,end); buffer=buffer.slice(end+2); if(!line.startsWith('data: ')) continue;
        const data = JSON.parse(line.slice(6));
        if(data.type==='delta') output.content.textContent += data.text;
        if(data.type==='sources' && data.sources.length) showSources(output.article,data.sources);
        if(data.type==='error') throw new Error(data.message);
        if(data.type==='done') done=true;
      }
    }
    if(!done) throw new Error('응답 스트림이 중단되었습니다.');
    await listConversations(); notice('응답과 출처를 저장했습니다.');
  } catch(error) { notice(error.message); } finally {busy=false; $('send').disabled=!token;}
};
document.querySelectorAll('[data-rating]').forEach(button => button.onclick = async () => {
  if(!conversation || busy) return; try { await json('/api/feedback', {conversation_id:conversation,rating:Number(button.dataset.rating)}); notice('피드백 저장 완료'); } catch(error) {notice(error.message);}
});
