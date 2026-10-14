// Drafts stay in memory in this browser tab. No CV/profile data or cloud upload.
export function defaultFields(vacancy) {
  return { employer: vacancy.employer || "", position: vacancy.title || "", recipient: "Recruitment Team", name: "", experience: "", motivation: "", focus: "" };
}
export function letterText(fields, date = new Date().toLocaleDateString("en-NZ", {day:"numeric",month:"long",year:"numeric"})) {
  const employer = fields.employer.trim() || "[Employer]";
  const position = fields.position.trim() || "[Position]";
  return `${date}\n\n${employer}\n\nDear ${fields.recipient.trim() || "Recruitment Team"},\n\nRe: ${position}\n\nPlease accept my application for the ${position} position at ${employer}.\n\n${fields.experience.trim() || "[Add your relevant experience and strengths, using only information from your CV.]"}\n\n${fields.motivation.trim() || "[Explain what interests you about this employer and role.]"}\n\n${fields.focus.trim() || "[Explain how your documented skills relate to the advertised requirements.]"}\n\nI would appreciate the opportunity to discuss the role and your roster requirements. Thank you for considering my application.\n\nYours sincerely,\n${fields.name.trim() || "[Your name]"}\n`;
}
const drafts = new Map();
export function clearLetterDrafts() {
  drafts.clear();
  if (typeof document !== "undefined") {
    document.getElementById("letter-fields")?.reset();
    const text=document.getElementById("letter-text");if(text)text.value="";
    document.getElementById("letter-editor")?.close();
  }
}
export function openLetterEditor(job) {
  const dialog = document.getElementById("letter-editor");
  const form = document.getElementById("letter-fields");
  const text = document.getElementById("letter-text");
  const message = document.getElementById("letter-message");
  const saved = drafts.get(job.id);
  const fields = saved?.fields || defaultFields(job.vacancy);
  for (const [key,value] of Object.entries(fields)) form.elements.namedItem(key).value=value;
  text.value=saved?.text || letterText(fields);
  message.textContent="Draft only. Check every claim and replace all bracketed prompts before applying. Closing keeps this draft until you sign out or reload.";
  const read = () => Object.fromEntries(Object.keys(fields).map(key=>[key,form.elements.namedItem(key).value]));
  const remember = () => drafts.set(job.id,{fields:read(),text:text.value});
  form.onsubmit=event=>event.preventDefault();
  dialog.oncancel=remember;
  form.oninput=remember; text.oninput=remember;
  document.getElementById("letter-build").onclick=()=>{
    if (text.value !== letterText(fields) && !confirm("Update the draft from the fields? This replaces any edits in the letter text.")) return;
    text.value=letterText(read());remember();
  };
  document.getElementById("letter-download").onclick=()=>{
    remember();
    const url=URL.createObjectURL(new Blob([text.value],{type:"text/markdown;charset=utf-8"}));
    const link=document.createElement("a");link.href=url;
    link.download=(read().employer+"_"+read().position+"_CoverLetter").replace(/[^A-Za-z0-9_-]+/g,"_").slice(0,160)+".md";
    link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    message.textContent="Draft downloaded. Review the text before submitting an application.";
  };
  document.getElementById("letter-copy").onclick=async()=>{
    try { await navigator.clipboard.writeText(text.value);message.textContent="Copied. You can paste the letter into Word or the employer's application form."; }
    catch { message.textContent="Copy unavailable. Select the letter text and copy it, or download the draft."; }
  };
  document.getElementById("letter-close").onclick=()=>{remember();dialog.close();};
  dialog.showModal();
}
