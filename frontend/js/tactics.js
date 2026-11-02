/* Football Career Legacy — elenco e calendário */
let squadData = null;
let selectedStarters = new Set();
let rosterCareerId = null;
const FORMATION_SLOTS = {"4-3-3": {GK:1,DEF:4,MID:3,ATT:3},"4-4-2":{GK:1,DEF:4,MID:4,ATT:2},"3-5-2":{GK:1,DEF:3,MID:5,ATT:2}};
const POS_ORDER = ["ATT","MID","DEF","GK"];
const POSITION_NAME = {GK:"Goleiro",DEF:"Defensor",MID:"Meio-campo",ATT:"Atacante"};
function rosterMessage(message, error=false) {
  const element=document.querySelector("#roster-feedback");
  element.textContent=message;
  element.classList.toggle("error",error);
}
function currentFormation(){return document.querySelector("#formation-select").value}
function currentSlots(){return FORMATION_SLOTS[currentFormation()]}
function eligibleLineup(ids) {
  if(ids.size !== 11) return false;
  const counts={GK:0,DEF:0,MID:0,ATT:0};
  for(const p of squadData.squad) if(ids.has(p.id)) counts[p.position]++;
  return Object.keys(counts).every(pos=>counts[pos]===currentSlots()[pos]);
}
function autofillLineup(){
  if(!squadData) return;
  selectedStarters = new Set();
  const slots=currentSlots();
  for(const pos of ["GK","DEF","MID","ATT"]){
    const ranked=squadData.squad.filter(p=>p.position===pos)
      .sort((a,b)=>(Number(b.starter)-Number(a.starter)) || b.rating-a.rating);
    ranked.slice(0,slots[pos]).forEach(p=>selectedStarters.add(p.id));
  }
  renderRoster();
}
async function loadSquad(cid){
  rosterCareerId=cid;
  const panel=document.querySelector("#squad-section");
  panel.classList.remove("hidden");
  panel.setAttribute("aria-busy","true");
  try {
    squadData=await request("/careers/"+cid+"/squad");
    document.querySelector("#formation-select").value=squadData.formation;
    document.querySelector("#tactic-select").value=squadData.tactic;
    const actual=new Set(squadData.squad.filter(p=>p.starter).map(p=>p.id));
    selectedStarters=actual;
    if(!eligibleLineup(actual)) autofillLineup();
    else renderRoster();
    rosterMessage("Selecione jogadores nos cards para trocar os titulares.");
  } catch(e){
    panel.classList.add("hidden");
    notify("Não foi possível carregar o elenco: "+e.message);
  } finally {panel.removeAttribute("aria-busy")}
}
function renderRoster(){
  if(!squadData) return;
  const field=document.querySelector("#tactical-field");
  field.replaceChildren();
  const names={ATT:"ATAQUE",MID:"MEIO-CAMPO",DEF:"DEFESA",GK:"GOLEIRO"};
  for(const pos of POS_ORDER) {
    const row=document.createElement("div");row.className="pitch-row";
    row.setAttribute("aria-label",names[pos]);
    squadData.squad.filter(p=>selectedStarters.has(p.id)&&p.position===pos)
      .forEach(p=>{
        const slot=document.createElement("div");slot.className="pitch-player";
        const shirt=document.createElement("div");shirt.className="pitch-shirt";
        shirt.textContent=p.rating;
        const label=document.createElement("span");label.textContent=p.name;
        slot.append(shirt,label);row.append(slot);
      });
    field.append(row);
  }
  const container=document.querySelector("#squad-cards");
  container.replaceChildren();
  const players=[...squadData.squad].sort((a,b)=>
    Number(selectedStarters.has(b.id))-Number(selectedStarters.has(a.id)) || b.rating-a.rating);
  for(const p of players){
    const active=selectedStarters.has(p.id);
    const card=document.createElement("button");
    card.type="button";
    card.className="roster-card"+(active?" on-field":"");
    card.setAttribute("aria-pressed",String(active));
    card.innerHTML='<span class="roster-badge">'+(active?"TITULAR":"RESERVA")+
      '</span><span class="roster-rating">'+escapeHTML(p.rating)+
      '</span><span class="roster-position">'+escapeHTML(POSITION_NAME[p.position])+
      '</span><strong>'+escapeHTML(p.name)+'</strong><small>'+
      escapeHTML(p.age)+' anos · '+escapeHTML(p.games ?? 0)+' jogos · '+
      escapeHTML(p.goals ?? 0)+' gols</small>';
    card.addEventListener("click",()=>toggleStarter(p.id));
    container.append(card);
  }
  const valid=eligibleLineup(selectedStarters);
  const button=document.querySelector("#save-lineup");
  button.disabled=!valid;
  const summary=Object.entries(currentSlots()).map(([pos,num])=>{
    const current=squadData.squad.filter(p=>selectedStarters.has(p.id)&&p.position===pos).length;
    return pos+": "+current+"/"+num;
  }).join(" · ");
  document.querySelector("#selection-count").textContent=selectedStarters.size+"/11 titulares · "+summary;
  document.querySelector("#selection-count").classList.toggle("invalid",!valid);
}
function toggleStarter(id){
  if(busy||!squadData)return;
  const p=squadData.squad.find(p=>p.id===id);
  if(!p)return;
  if(selectedStarters.has(id))selectedStarters.delete(id);
  else {
    const byPos=squadData.squad.filter(x=>selectedStarters.has(x.id)&&x.position===p.position);
    if(byPos.length>=currentSlots()[p.position]){
      rosterMessage("Limite de "+POSITION_NAME[p.position]+"s atingido. Retire um titular dessa posição primeiro.",true);
      return;
    }
    selectedStarters.add(id);
  }
  rosterMessage("Escalação alterada. Salve para aplicar no jogo.");
  renderRoster();
}
async function saveLineup(){
  if(busy||rosterCareerId===null||!squadData)return;
  if(!eligibleLineup(selectedStarters)) {
    rosterMessage("A escalação precisa ter exatamente 11 atletas nas posições da formação.",true);
    return;
  }
  busy=true;
  const button=document.querySelector("#save-lineup");button.disabled=true;
  try {
    await request("/careers/"+rosterCareerId+"/lineup",{
      method:"PUT",
      body:JSON.stringify({formation:currentFormation(),tactic:document.querySelector("#tactic-select").value,
        starters:[...selectedStarters]})
    });
    await loadSquad(rosterCareerId);
    rosterMessage("Escalação e tática salvas com sucesso!");
    notify("Escalação salva!",true);
  }catch(e){rosterMessage(e.message,true)}
  finally{busy=false;button.disabled=false}
}
async function loadFixtures(cid){
  const area=document.querySelector("#fixtures-list");
  area.textContent="Carregando partidas...";
  try {
    const data=await request("/careers/"+cid+"/fixtures?mine=true");
    area.replaceChildren();
    if(!data.length){area.textContent="Nenhuma partida encontrada.";return}
    for(const fixture of data){
      const item=document.createElement("div");item.className="fixture-item";
      const round=document.createElement("span");round.className="fixture-round";round.textContent="RODADA "+fixture.round;
      const matchup=document.createElement("strong");
      matchup.textContent=fixture.home+" × "+fixture.away;
      const score=document.createElement("span");score.className="fixture-score";
      score.textContent=fixture.played ? fixture.home_goals+" × "+fixture.away_goals:"A disputar";
      item.append(round,matchup,score);area.append(item);
    }
  }catch(e){area.textContent="Falha ao carregar calendário: "+e.message}
}
document.querySelector("#formation-select").addEventListener("change",()=>{
  autofillLineup();
  rosterMessage("Nova formação selecionada. Confira os titulares e salve.");
});
document.querySelector("#tactic-select").addEventListener("change",()=>
  rosterMessage("Tática alterada. Salve para aplicar ao jogo."));
document.querySelector("#auto-lineup").addEventListener("click",()=>{
  autofillLineup();rosterMessage("Escalação automática preparada. Salve para aplicar.");
});
document.querySelector("#save-lineup").addEventListener("click",saveLineup);
