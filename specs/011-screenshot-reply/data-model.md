# Data model
Temporary session: images[{id,name,dataUrl,size}], text, analysis{recognizedText,summaryZh,language,directions[{id,title,description}],warnings[]}, selectedDirection?, customInstruction, language, result{draftText,translationZh,missingInformation[],conflictNote}, editedText, saved flag, busy/error.
States: empty -> analyzing -> choosing -> generating -> editing. Errors retain input. Source changes invalidate downstream analysis/result; changing intent clears old result; modifying text requires fresh analysis or custom-only generation. Unmount ignores outstanding responses.
Existing conversation ID is only navigation context; no new persistence entities. Never submit image data to the manual-draft endpoint.
