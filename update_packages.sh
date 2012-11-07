#!/bin/bash

dirs_repos="
User https://johnburnett@github.com/johnburnett/sublime-user-settings.git
footools https://johnburnett@github.com/johnburnett/sublime-footools.git
WordHighlight https://github.com/SublimeText/WordHighlight.git
Theme\ -\ Soda https://github.com/buymeasoda/soda-theme.git
CoffeeScript https://github.com/jashkenas/coffee-script-tmbundle.git
HexViewer https://github.com/facelessuser/HexViewer.git
ColorPicker https://github.com/weslly/ColorPicker.git
SmartCursor https://github.com/bizoo/SmartCursor.git
"

pushd .. > /dev/null

echo "$dirs_repos" | while read dir repo ; do
	if [ -z "$dir" ]
	then
		continue
	fi

	echo $dir
	if [ -e "$dir" ]
	then
		pushd "$dir" > /dev/null
		git pull
		popd > /dev/null
	else
		git clone "$repo" "$dir"
	fi
	echo "----"
done

popd > /dev/null
