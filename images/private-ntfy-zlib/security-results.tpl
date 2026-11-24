[
{{- range $i, $r := . -}}
{{if $i}},{{end}}{"Target":{{toJson $r.Target}},"Class":{{toJson $r.Class}},"Type":{{toJson $r.Type}},"Packages":{{toJson $r.Packages}},"Vulnerabilities":{{toJson $r.Vulnerabilities}},"Secrets":[
{{- range $j, $s := $r.Secrets -}}
{{if $j}},{{end}}{"RuleID":{{toJson $s.RuleID}},"Category":{{toJson $s.Category}},"Severity":{{toJson $s.Severity}},"StartLine":{{$s.StartLine}},"EndLine":{{$s.EndLine}}}
{{- end -}}]}
{{- end -}}]
