#!/bin/bash
# <xbar.title>Claude usage</xbar.title>
# <xbar.desc>Limiti di utilizzo di Claude (5 ore e settimanale) letti dalla status line di Claude Code</xbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:$PATH"
state="$HOME/.claude/usage-state.json"

if [ ! -s "$state" ]; then
  echo "✦ –"
  echo "---"
  echo "Nessun dato ancora"
  echo "Manda un messaggio in Claude Code per popolarlo"
  exit 0
fi

IFS=$'\t' read -r fh fhr sd sdr age <<<"$(jq -r --argjson now "$(date +%s)" '
  def ep: if . == null then null elif type == "number" then . else (sub("\\.[0-9]+"; "") | fromdateiso8601) end;
  def pct($w): if $w == null or $w.used_percentage == null then ""
               elif ($w.resets_at|ep) != null and ($w.resets_at|ep) <= $now then "0"
               else ($w.used_percentage|floor|tostring) end;
  def when($w; $f): ($w.resets_at|ep) as $e | if $e == null then "—" else ($e|localtime|strftime($f)) end;
  [ pct(.five_hour), when(.five_hour; "%H:%M"),
    pct(.seven_day), when(.seven_day; "%d/%m alle %H:%M"),
    ((($now - .updated_at) / 60) | floor | tostring) ] | @tsv
' "$state")"

color() {
  [ -z "$1" ] && return
  if [ "$1" -ge 90 ]; then echo " | color=#E5484D"
  elif [ "$1" -ge 70 ]; then echo " | color=#F5A524"
  fi
}

# Riga nella barra dei menu
echo "✦ ${fh:-?}%$(color "$fh")"
echo "---"
echo "Sessione 5 ore: ${fh:-?}% · si azzera alle $fhr$(color "$fh")"
echo "Settimanale: ${sd:-?}% · si azzera il $sdr$(color "$sd")"
echo "---"
if [ "$age" -lt 1 ]; then
  echo "Aggiornato ora | size=11"
else
  echo "Aggiornato $age min fa (all'ultimo uso di Claude Code) | size=11"
fi
echo "Aggiorna | refresh=true"
