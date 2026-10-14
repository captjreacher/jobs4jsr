import test from "node:test";
import assert from "node:assert/strict";
import { defaultFields, letterText } from "../public/cover-letter.js";
test("default draft identifies the vacancy and prompts for unsupported personal information",()=>{
  const fields=defaultFields({employer:"Example Café",title:"FOH Team Member"});
  const text=letterText(fields,"14 October 2026");
  assert.match(text,/FOH Team Member position at Example Café/);
  assert.match(text,/\[Add your relevant experience/);
  assert.match(text,/\[Your name\]/);
  assert.doesNotMatch(text,/barista qualification|work rights|available immediately/i);
});
test("editable fields populate the letter without changing the original vacancy",()=>{
  const vacancy={employer:"Example Café",title:"FOH"};const fields=defaultFields(vacancy);
  Object.assign(fields,{employer:"Auckland Venue",recipient:"Alex",name:"Jess",experience:"I supported hotel guests.",motivation:"I enjoy welcoming guests.",focus:"I work carefully with the team."});
  const text=letterText(fields,"14 October 2026");
  for(const phrase of ["Dear Alex,","Auckland Venue","I supported hotel guests.","I enjoy welcoming guests.","I work carefully with the team.","Yours sincerely,\nJess"])assert.ok(text.includes(phrase));
  assert.equal(vacancy.employer,"Example Café");assert.doesNotMatch(text,/\[/);
});
