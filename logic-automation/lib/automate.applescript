-- Earworm / Logic Pro UI automation
-- Drives Logic Pro 12 to: new empty project (+SI track), add audio track,
-- import an mp3, apply region tempo to project, analyze chords + key,
-- stem-split (all stems), and Save As into the earworm directory.
--
-- Args: 1 = mp3 path, 2 = project name ("<Artist> - <Song>"), 3 = save directory
--
-- Notes learned from the live UI:
--  * Logic's modern dialog buttons often have flaky AX references; pressing the
--    default key (return) is the reliable way to confirm. We try AXPress first,
--    fall back to return.
--  * Key analysis can pop a "Key signature changed" confirmation; we answer No.
--  * Stem split shows a "Splitting" progress window titled "Logic Pro".

on run argv
	set mp3Path to item 1 of argv
	set projName to item 2 of argv
	set saveDir to item 3 of argv
	-- Optional 4th arg = a test settle (seconds): run key analysis that many
	-- seconds after chords and SKIP stem-splitting, for fast key-analysis tests.
	-- Omitted/-1 = full production flow (stem split, then key).
	set testSettle to -1
	if (count of argv) ≥ 4 then set testSettle to (item 4 of argv) as integer

	tell application "System Events"
		if not (exists process "Logic Pro") then error "Logic Pro is not running"
		tell process "Logic Pro"
			set frontmost to true
		end tell
	end tell

	my step("Creating empty project")
	my handleProjectChooser()
	my handleNewTracksSheet()

	my step("Adding audio track")
	my clickMenu({"Track", "New Audio Track"})
	delay 0.8

	my step("Importing audio file")
	my importAudio(mp3Path)

	my step("Applying region tempo to project tempo")
	my selectAllRegions()
	my applyRegionTempo()

	my step("Analyzing chords")
	my selectAllRegions()
	my keyCmd("2")
	my trace("sent ⌃⌥⌘2 (analyze chords) — waiting for it to finish…")
	my waitIdle(600)

	-- Key analysis no-ops until the chord analysis has fully committed; a ~30s
	-- settle after chords lets ⌃⌥⌘3 fire reliably (verified — no stem-split needed).
	-- A test settle (4th arg) overrides it; test mode also skips stem-splitting.
	set keySettle to 30
	if testSettle ≥ 0 then set keySettle to testSettle
	my step("Analyzing key signature (settling " & keySettle & "s so chords commit)")
	delay keySettle
	my selectAllRegions()
	my keyCmd("3")
	my trace("sent ⌃⌥⌘3 (analyze key signature) after a " & keySettle & "s settle")
	my handleKeySignatureDialog()
	my waitIdle(600)

	if testSettle < 0 then
		my step("Stem splitting (all stems)")
		my selectAllRegions()
		my keyCmd("4")
		my trace("sent ⌃⌥⌘4 — stem splitting (this takes a while)…")
		delay 1.0
		my waitIdle(1800)
	end if

	my step("Saving project")
	my saveAs(projName, saveDir)

	my step("DONE")
	return "OK"
end run

----------------------------------------------------------------------
-- Project chooser: select default (Empty Project) and click Choose
----------------------------------------------------------------------
on handleProjectChooser()
	my trace("waiting for the 'Choose a Project' window…")
	tell application "System Events" to tell process "Logic Pro"
		-- Wait for either the chooser or an already-open Tracks window, clearing any
		-- startup modal (e.g. "audio device not available") that would block it.
		repeat 60 times
			my dismissStartupAlert()
			if (exists window "Choose a Project") then exit repeat
			if (exists (first window whose name contains "Tracks")) then
				-- A project opened directly (no chooser). Make a new one.
				my trace("no chooser — a project opened; using File ▸ New")
				my clickMenu({"File", "New"})
				delay 1.0
				exit repeat
			end if
			delay 0.5
		end repeat
		if (exists window "Choose a Project") then
			-- The chooser can open on "Recent" — where Choosing would REOPEN the most
			-- recent project. Make sure the sidebar is on "New Project" first.
			my selectNewProjectTab()
			my trace("chooser on New Project — clicking Choose (Empty Project)")
			try
				click button "Choose" of group 2 of splitter group 1 of window "Choose a Project"
			on error
				set frontmost to true
				keystroke return
			end try
		end if
	end tell
	delay 1.2
end handleProjectChooser

-- Select the "New Project" row in the chooser sidebar (it may open on "Recent").
-- The sidebar is an outline whose rows hold a cell named after the section.
on selectNewProjectTab()
	tell application "System Events" to tell process "Logic Pro"
		try
			set ol to outline 1 of scroll area 1 of splitter group 1 of window "Choose a Project"
			repeat with r in (rows of ol)
				set isNew to false
				try
					if (name of (UI element 1 of r)) is "New Project" then set isNew to true
				end try
				if not isNew then
					try
						repeat with s in (static texts of (UI element 1 of r))
							if (value of s) is "New Project" then set isNew to true
						end repeat
					end try
				end if
				if isNew then
					try
						select r
					end try
					try
						if not (selected of r) then click (UI element 1 of r)
					end try
					my trace("selected the 'New Project' sidebar tab")
					delay 0.7
					return
				end if
			end repeat
			my trace("⚠ could not find the 'New Project' sidebar row")
		on error errMsg
			my trace("⚠ chooser sidebar not found: " & errMsg)
		end try
	end tell
end selectNewProjectTab

----------------------------------------------------------------------
-- New Tracks sheet: default is Software Instrument; confirm with Create
----------------------------------------------------------------------
on handleNewTracksSheet()
	my trace("waiting for the 'New Tracks' dialog on the Tracks window…")
	tell application "System Events" to tell process "Logic Pro"
		-- Wait (guarded — the lookup throws if no such window yet) for the Tracks
		-- window to carry the New Tracks sheet, clearing any startup alert meanwhile.
		repeat 90 times
			my dismissStartupAlert()
			if (exists (first window whose name contains "Tracks")) then
				if (count of sheets of (first window whose name contains "Tracks")) > 0 then exit repeat
			end if
			delay 0.4
		end repeat
		-- Click Create, retrying until the sheet actually closes (a stray alert or a
		-- flaky button press can leave it up — the old code fired once and moved on).
		repeat 15 times
			my dismissStartupAlert()
			if not (exists (first window whose name contains "Tracks")) then exit repeat
			set w to (first window whose name contains "Tracks")
			if (count of sheets of w) = 0 then exit repeat
			my trace("New Tracks dialog up — clicking Create (Software Instrument)")
			try
				perform action "AXPress" of button "Create" of sheet 1 of w
			on error
				try
					click button "Create" of sheet 1 of w
				on error
					set frontmost to true
					keystroke return
				end try
			end try
			delay 0.7
		end repeat
	end tell
	delay 1.0
end handleNewTracksSheet

-- Some Logic launches pop a modal before the project chooser — most often "the
-- audio device is not available" when the last-used interface is gone. Clear it
-- (its default button, else Return) so startup can proceed. Only alert/dialog
-- windows are targeted; the chooser and New-Tracks sheet are handled elsewhere,
-- and the tempo/key alerts come later in the run.
on dismissStartupAlert()
	tell application "System Events" to tell process "Logic Pro"
		set a to missing value
		try
			set a to (first window whose description is "alert")
		end try
		if a is missing value then
			try
				set a to (first window whose subrole is "AXDialog" and name is not "Choose a Project")
			end try
		end if
		if a is missing value then return
		my trace("clearing a startup modal: '" & (name of a) & "'")
		my clickDefaultButton(a)
		delay 0.4
	end tell
end dismissStartupAlert

-- Press a window's default (highlighted) button; fall back to Return.
on clickDefaultButton(win)
	tell application "System Events" to tell process "Logic Pro"
		try
			repeat with b in (buttons of win)
				try
					if (value of attribute "AXDefaultButton" of b) is true then
						perform action "AXPress" of b
						return
					end if
				end try
			end repeat
		end try
		set frontmost to true
		keystroke return
	end tell
end clickDefaultButton

----------------------------------------------------------------------
-- Import audio file via File > Import > Audio File, drive the open panel
----------------------------------------------------------------------
on importAudio(mp3Path)
	my trace("opening File ▸ Import ▸ Audio File…")
	tell application "System Events" to tell process "Logic Pro"
		set frontmost to true
		repeat 12 times
			try
				click menu item "Audio File…" of menu 1 of menu item "Import" of menu "File" of menu bar 1
				exit repeat
			on error
				key code 53
				delay 1.0
			end try
		end repeat
		-- Wait for the Open File panel
		repeat 30 times
			if (exists window "Open File") then exit repeat
			delay 0.3
		end repeat
		my trace("open panel up — typing the file path")
		delay 0.4
		-- Go to folder: type the full path
		keystroke "g" using {command down, shift down}
		delay 0.6
		keystroke mp3Path
		delay 0.4
		keystroke return
		delay 0.8
		-- Confirm the open
		my trace("confirming import (Open)")
		try
			click button "Open" of window "Open File"
		on error
			keystroke return
		end try
	end tell
	-- Handle optional "audio file contains tempo information" dialog
	my trace("watching for the 'contains tempo information' dialog…")
	delay 0.8
	my dismissTempoInfoDialog()
	delay 0.6
end importAudio

-- If Logic asks about embedded tempo info, choose "Don't Import" (keep project
-- tempo). The button is "Don’t Import" with a CURLY apostrophe, so we match by
-- prefix "Don". The alert can appear a couple seconds after the import, and it
-- is modal, so we must clear it before anything else — poll up to ~15s.
on dismissTempoInfoDialog()
	tell application "System Events" to tell process "Logic Pro"
		repeat 30 times
			if (exists (first window whose description is "alert")) then
				set dlg to (first window whose description is "alert")
				try
					set b to (first button of dlg whose name starts with "Don")
					my trace("tempo-info dialog appeared — clicking Don't Import")
					try
						perform action "AXPress" of b
					on error
						click b
					end try
					-- confirm it closed
					delay 0.4
					if not (exists (first window whose description is "alert")) then return
				on error
					-- some other alert; leave it for a dedicated handler
					return
				end try
			end if
			delay 0.5
		end repeat
	end tell
end dismissTempoInfoDialog

----------------------------------------------------------------------
-- Apply Region Tempo to Project Tempo (Edit > Tempo > ...)
----------------------------------------------------------------------
on applyRegionTempo()
	my trace("opening Edit ▸ Tempo ▸ Apply Region Tempo… (waiting for Logic to free the menu bar)")
	tell application "System Events" to tell process "Logic Pro"
		set frontmost to true
		-- Right after importing a long file Logic can be too busy to serve the menu
		-- bar (-1728). Retry, pressing Escape to clear any half-opened menu first.
		set okMenu to false
		repeat 12 times
			try
				click menu item "Apply Region Tempo to Project Tempo…" of menu 1 of menu item "Tempo" of menu "Edit" of menu bar 1
				set okMenu to true
				exit repeat
			on error
				my trace("…menu bar busy, retrying in 1s")
				key code 53 -- escape
				delay 1.0
			end try
		end repeat
		if okMenu then my trace("Apply Region Tempo dialog requested — confirming")
		repeat 20 times
			if (exists window "Apply Region Tempo to Project Tempo") then exit repeat
			delay 0.2
		end repeat
		if (exists window "Apply Region Tempo to Project Tempo") then
			try
				click button "Apply" of window "Apply Region Tempo to Project Tempo"
			on error
				keystroke return
			end try
		end if
	end tell
	delay 1.0
end applyRegionTempo

----------------------------------------------------------------------
-- Key signature analysis may ask whether chords should follow. Answer No.
----------------------------------------------------------------------
on handleKeySignatureDialog()
	tell application "System Events" to tell process "Logic Pro"
		repeat 12 times
			set dlg to my frontDialog()
			if dlg is not missing value then
				if (exists button "No" of dlg) then
					my trace("'Key signature changed' dialog — answering No")
					try
						click button "No" of dlg
					on error
						set frontmost to true
						keystroke return
					end try
					return
				end if
			end if
			delay 0.3
		end repeat
	end tell
end handleKeySignatureDialog

----------------------------------------------------------------------
-- Save As into <saveDir>/<projName> as a project folder, copying assets
----------------------------------------------------------------------
on saveAs(projName, saveDir)
	my trace("opening File ▸ Save As…")
	tell application "System Events" to tell process "Logic Pro"
		set frontmost to true
		repeat 12 times
			try
				click menu item "Save As…" of menu "File" of menu bar 1
				exit repeat
			on error
				key code 53
				delay 1.0
			end try
		end repeat
		-- The save dialog is a standalone window named "Save" (NOT a sheet)
		repeat 30 times
			if (exists window "Save") then exit repeat
			delay 0.3
		end repeat
		set sv to window "Save"
		my trace("Save dialog up — name='" & projName & "', folder='" & saveDir & "'")
		delay 0.4
		-- Set the project name (first text field; default value is "Project")
		try
			set tf to text field 1 of sv
			set focused of tf to true
			keystroke "a" using {command down}
			set value of tf to projName
		on error
			keystroke projName
		end try
		delay 0.3
		-- Ensure project is organized as a Folder (matches existing songs)
		try
			click radio button "Folder" of sv
		end try
		-- "Copy Audio files" is on by default; leave asset checkboxes as-is.
		delay 0.2
		-- Choose destination folder via Go-to-folder
		keystroke "g" using {command down, shift down}
		delay 0.6
		keystroke saveDir
		delay 0.4
		keystroke return
		delay 0.8
		-- Commit the save
		try
			click button "Save" of sv
		on error
			keystroke return
		end try
	end tell
	-- A "replace existing?" prompt may appear
	delay 1.0
	my confirmReplaceIfPresent()
	my waitIdle(120)
end saveAs

-- When the target project folder already exists, Logic shows an "…already
-- exists. Replace?" confirmation as a SHEET on the Save window (not a top-level
-- dialog). We overwrite. If the Save window closes without a prompt, the save
-- went through cleanly and we're done.
on confirmReplaceIfPresent()
	tell application "System Events" to tell process "Logic Pro"
		repeat 30 times
			if not (exists window "Save") then return -- saved, no replace needed
			if (count of sheets of window "Save") > 0 then
				set sh to sheet 1 of window "Save"
				if (exists button "Replace" of sh) then
					try
						perform action "AXPress" of button "Replace" of sh
					on error
						click button "Replace" of sh
					end try
					return
				end if
			end if
			delay 0.3
		end repeat
	end tell
end confirmReplaceIfPresent

----------------------------------------------------------------------
-- Helpers
----------------------------------------------------------------------

-- Select all regions in the arrange area (only the audio region exists)
on selectAllRegions()
	tell application "System Events" to tell process "Logic Pro"
		set frontmost to true
		-- Raise the main Tracks window so the arrange has key focus. Without this a
		-- floating window (or lost app focus) can eat the ⌃⌥⌘ analysis commands.
		try
			perform action "AXRaise" of (first window whose name contains "Tracks")
		end try
		delay 0.25
		keystroke "a" using {command down}
	end tell
	delay 0.3
end selectAllRegions

-- Send a custom key command: control+option+command+<key>
on keyCmd(theKey)
	tell application "System Events" to tell process "Logic Pro"
		set frontmost to true
		delay 0.2
		keystroke theKey using {control down, option down, command down}
	end tell
end keyCmd

-- Click a menu bar path like {"Track","New Audio Track"} or nested deeper
on clickMenu(pathList)
	tell application "System Events" to tell process "Logic Pro"
		set frontmost to true
		set topName to item 1 of pathList
		set itemName to item 2 of pathList
		-- Logic can be momentarily too busy to serve the menu bar (-1728); retry.
		repeat 12 times
			try
				click menu item itemName of menu topName of menu bar 1
				return
			on error
				key code 53 -- escape any half-opened menu
				delay 1.0
			end try
		end repeat
	end tell
end clickMenu

-- Return the frontmost dialog-like window, or missing value
on frontDialog()
	tell application "System Events" to tell process "Logic Pro"
		try
			set fw to front window
			return fw
		on error
			return missing value
		end try
	end tell
end frontDialog

-- Wait until Logic is idle: the main Tracks window is front and no progress
-- window ("Logic Pro" titled) is showing. Times out after maxSecs.
on waitIdle(maxSecs)
	set n to maxSecs * 2
	repeat n times
		tell application "System Events" to tell process "Logic Pro"
			set fn to ""
			try
				set fn to name of front window
			end try
		end tell
		if fn contains "Tracks" then return true
		delay 0.5
	end repeat
	return false
end waitIdle

on step(msg)
	log "[logic] " & msg
end step

-- finer-grained sub-step trace (indented) so progress is visible live
on trace(msg)
	log "[logic]    · " & msg
end trace
