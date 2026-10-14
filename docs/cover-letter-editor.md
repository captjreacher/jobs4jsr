# Saved-job cover-letter editor

On the live board, save a job and open **Saved**. Its actions are **Unsave**, **Dismiss**, **Create cover letter**, and **Applied**. The editor is available for saved, non-dismissed jobs.

Create cover letter opens a real editable dialog. Employer and exact position are pre-filled from the vacancy. Fill hiring contact, your name, relevant experience, why this employer and how you meet the advertised requirements. Select **Update draft from fields**, then edit the letter text directly. Updating an already edited letter asks before replacing its text. The default New Zealand English template follows a concise greeting, application introduction, experience, employer-specific interest, requirements, thank-you and closing structure.

Only employer/title and the greeting are populated automatically. Personal-experience sections use explicit prompts until Jess fills them from her CV; the browser does not claim undocumented skills, availability or work rights. The private CV/profile/templates and existing local Word letters are not published in static assets or uploaded. This is a browser template editor, not an external AI generator or hosted-letter Storage activation.

Copy the letter to Word/an application form or download a Markdown draft. It is never automatically submitted. Replace all bracketed prompts and review every claim before using it. Existing local Word letters remain available through the local report.

Drafts are kept only in memory in the current tab, separately per job. Closing/Escape preserves the draft within that tab; reload, sign-out or denied session access clears it. No localStorage or cloud draft persistence is used. Download or copy before reloading. Hosted uploads remain disabled.

Validation: two template tests and ten existing Worker behaviour tests pass. Live Saved view displayed the four requested actions for the existing saved Novotel vacancy; editor opened with matching employer/title, fields updated the draft, and Markdown download succeeded. Mobile dialog fits a 390px viewport with scrollable fields/text. No job decision, membership, vacancy or schedule changes were needed for this feature. Existing Worker/secrets/custom domains are retained.
