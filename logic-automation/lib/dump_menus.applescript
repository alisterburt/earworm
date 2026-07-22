-- Dump Logic Pro's full menu bar tree (top level + one submenu level).
-- Usage: osascript dump_menus.applescript "Menu Name"   (omit arg = all top-level menus)
on run argv
	set targetMenu to ""
	if (count of argv) > 0 then set targetMenu to item 1 of argv
	set out to ""
	tell application "System Events" to tell process "Logic Pro"
		set barItems to menu bar items of menu bar 1
		repeat with bi in barItems
			set mname to name of bi
			if mname is not missing value then
				if targetMenu is "" or mname is targetMenu then
					set out to out & "=== " & mname & " ===" & linefeed
					try
						set theMenu to menu 1 of bi
						set out to out & my dumpMenu(theMenu, "  ")
					end try
				end if
			end if
		end repeat
	end tell
	return out
end run

on dumpMenu(theMenu, indent)
	set out to ""
	tell application "System Events"
		set items_ to menu items of theMenu
		repeat with mi in items_
			set iname to name of mi
			if iname is missing value then
				set out to out & indent & "----" & linefeed
			else
				set en to enabled of mi
				set mark to "  "
				if en is false then set mark to "x "
				set out to out & indent & mark & iname & linefeed
				try
					set sub to menu 1 of mi
					set out to out & my dumpMenu(sub, indent & "    ")
				end try
			end if
		end repeat
	end tell
	return out
end dumpMenu
