/* Player profile and offers: all values come from the existing API. */
function playerStats(title, values, average) {
  return '<h3 class="subheading">'+escapeHTML(title)+'</h3><div class="stats-grid">'+
    stat("JOGOS", values.games ?? 0)+stat("GOLS", values.goals ?? 0)+
    stat("ASSISTÊNCIAS", values.assists ?? 0)+stat("NOTA MÉDIA", average == null ? "—" : Number(average).toFixed(2))+'</div>';
}
function renderPlayerProfile(p, career) {
  const history = p.history || [];
  const season = history.find(h => h.season === career.season) || {};
  const totals = p.career_totals || {};
  const games = history.reduce((sum,h) => sum+h.games,0);
  const average = games ? history.reduce((sum,h) => sum+h.avg_rating*h.games,0)/games : null;
  return '<article class="player-profile pos-'+escapeHTML(p.position)+'">'+
    '<div class="profile-overall"><strong>'+escapeHTML(p.rating)+'</strong><span>OVERALL · '+escapeHTML(p.position)+'</span></div>'+
    '<div><span class="eyebrow">SEU LEGADO · TEMPORADA '+escapeHTML(career.season)+'</span>'+
    '<h2>'+escapeHTML(p.name)+'</h2><p>'+escapeHTML(p.club || "Sem clube")+' · '+escapeHTML(p.age)+' anos · '+escapeHTML(POSITION_NAME[p.position] || p.position)+'</p>'+
    '<p>Potencial <b>'+escapeHTML(p.potential)+'</b> · Valor <b>'+escapeHTML(p.value_millions)+' M</b></p>'+
    '<span class="career-status">'+escapeHTML({ACTIVE:"Em atividade",RETIRED:"Aposentado",FIRED:"Carreira encerrada"}[career.status] || career.status)+'</span></div></article>'+
    playerStats("TEMPORADA ATUAL",season,season.avg_rating)+
    (!season.games ? '<p class="empty-state">Você ainda não disputou partidas nesta temporada. Suas estatísticas aparecerão após entrar em campo.</p>' : '')+
    playerStats("TOTAIS DA CARREIRA",totals,average)+
    '<h3 class="subheading">HISTÓRICO POR TEMPORADA</h3>'+
    (history.length ? '<div class="table-wrap"><table><thead><tr><th>TEMPORADA</th><th>JOGOS</th><th>GOLS</th><th>ASSISTÊNCIAS</th><th>NOTA</th></tr></thead><tbody>'+
      history.map(h=>'<tr>'+[h.season,h.games,h.goals,h.assists,Number(h.avg_rating).toFixed(2)].map(v=>'<td>'+escapeHTML(v)+'</td>').join('')+'</tr>').join('')+
      '</tbody></table></div>' : '<p class="empty-state">Seu histórico será construído com as partidas disputadas.</p>');
}
async function loadPlayerCareer(career) {
  const panel = $("#player-section");
  panel.classList.remove("hidden");
  panel.innerHTML = '<p role="status">Carregando perfil e propostas...</p>';
  const results = await Promise.allSettled([
    request('/careers/'+career.id+'/player'), request('/careers/'+career.id+'/offers')
  ]);
  if (currentCareerId !== career.id || activeCareer !== career) return;
  panel.replaceChildren();
  const profile=document.createElement("div");
  if(results[0].status === "fulfilled") {
    profile.innerHTML=renderPlayerProfile(results[0].value,career);
    $("#dashboard-content").innerHTML = '<p>Temporada '+escapeHTML(career.season)+' · Rodada '+escapeHTML(career.round)+' de '+escapeHTML(career.total_rounds)+'</p>';
  } else profile.textContent="Não foi possível carregar o perfil. Atualize para tentar novamente.";
  panel.append(profile);
  const market=document.createElement("section"); market.className="player-market";
  market.innerHTML='<div class="section-heading"><h3>MERCADO DE TRANSFERÊNCIAS</h3></div>';
  panel.append(market);
  if(results[1].status !== "fulfilled") {
    const error=document.createElement("p");error.className="empty-state";
    error.textContent="Não foi possível carregar as propostas. Tente atualizar novamente.";market.append(error);
  } else {
    const data=results[1].value;
    const pending=data.offers.filter(o=>o.status==="PENDING").length;
    const status=document.createElement("p");status.className="window-status";
    status.textContent=(data.transfer_window ? "● Janela aberta" : "○ Janela fechada")+" · "+pending+" proposta(s) pendente(s)";
    market.append(status);
    const help=document.createElement("p");help.className="market-help";
    help.textContent=career.status!=="ACTIVE" ? "Esta carreira está encerrada. As propostas ficam disponíveis apenas para consulta." :
      "A janela abre antes das rodadas 1 e 8. Aceitar uma proposta muda seu clube e encerra as outras propostas pendentes.";
    market.append(help);
    const cards=document.createElement("div");cards.className="offers-grid";market.append(cards);
    if(!data.offers.length) cards.innerHTML='<p class="empty-state">'+(data.transfer_window ? "Nenhuma proposta recebida nesta temporada. Continue jogando e evoluindo seu atleta." : "Nenhuma proposta nesta temporada. Acompanhe a próxima janela de transferências.")+'</p>';
    const labels={PENDING:"Pendente",ACCEPTED:"Aceita",REJECTED:"Recusada",EXPIRED:"Expirada"};
    for(const offer of data.offers) {
      const card=document.createElement("article");card.className="offer-card";
      card.innerHTML='<span class="roster-badge">'+escapeHTML(labels[offer.status] || offer.status)+'</span>'+
        '<h3>'+escapeHTML(offer.club)+'</h3><p>'+escapeHTML(offer.role === "TITULAR" ? "Titular" : "Reserva")+' no elenco</p>'+
        '<div class="offer-details"><span>Força <b>'+escapeHTML(offer.team_strength)+'</b></span><span>Última classificação <b>'+escapeHTML(offer.last_position == null ? "Não disponível" : offer.last_position+"º")+'</b></span></div>';
      const button=document.createElement("button");button.className="primary-btn";
      button.textContent=offer.status==="PENDING" ? "ACEITAR PROPOSTA ↗" : labels[offer.status] || offer.status;
      button.disabled=!data.transfer_window || offer.status!=="PENDING" || career.status!=="ACTIVE";
      button.addEventListener("click",()=>acceptPlayerOffer(career,offer));
      card.append(button);cards.append(card);
    }
  }
  const retry=document.createElement("button");retry.className="small-btn";retry.textContent="ATUALIZAR PERFIL E PROPOSTAS ↻";
  retry.addEventListener("click",()=>{if(!busy) loadPlayerCareer(career)});panel.append(retry);
}
async function acceptPlayerOffer(career,offer) {
  if(busy || currentCareerId!==career.id || career.status!=="ACTIVE") return;
  if(!confirm("Aceitar a proposta de "+offer.club+" como "+offer.role.toLowerCase()+"? Você mudará de clube e as demais propostas pendentes serão recusadas.")) return;
  busy=true;
  document.querySelectorAll("#player-section button").forEach(b=>b.disabled=true);
  $("#advance-btn").disabled=true;
  try {
    const result=await request('/careers/'+career.id+'/offers/'+offer.id+'/accept',{method:"POST"});
    await openCareer(career.id);
    notify(result.message || "Transferência concluída!",true);
  } catch(error) {
    await openCareer(career.id);
    notify(error.message);
  } finally {
    busy=false;
    $("#advance-btn").disabled=activeCareer?.status!=="ACTIVE";
  }
}
