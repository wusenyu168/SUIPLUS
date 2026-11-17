package sub

import (
	"fmt"
	"net"
	"strings"

	"github.com/admin8800/s-ui/logger"
	"github.com/admin8800/s-ui/service"
	"github.com/admin8800/s-ui/util"

	"gopkg.in/yaml.v3"
)

type ClashService struct {
	service.SettingService
	JsonService
	LinkService
}

const basicClashConfig = `mixed-port: 7890
allow-lan: false
mode: rule
log-level: info
external-controller: 127.0.0.1:9090
tun:
  enable: true
  stack: system
  auto-route: true
  auto-detect-interface: true
  dns-hijack:
    - any:53
dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver:
    - 8.8.8.8
    - 1.1.1.1
  nameserver:
    - https://1.1.1.1/dns-query
    - https://dns.google/dns-query
    - https://doh.pub/dns-query
  # Proxy hostnames must use DoH: ISP DNS pollutes panel + CF/Argo domains to 28.0.4.x.
  proxy-server-nameserver:
    - https://1.1.1.1/dns-query
    - https://dns.google/dns-query
  nameserver-policy:
    "node.qianrenzu.top":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "+.qianrenzu.top":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "cf.090227.xyz":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "+.090227.xyz":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "cloudflare.182682.xyz":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "+.182682.xyz":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "+.trycloudflare.com":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
    "+.cloudflare.com":
      - https://1.1.1.1/dns-query
      - https://dns.google/dns-query
  fallback:
    - https://1.0.0.1/dns-query
    - tcp://9.9.9.9:53
  fake-ip-filter:
    - "*.lan"
    - localhost
    - "*.local"
    - "node.qianrenzu.top"
    - "+.qianrenzu.top"
    - "cf.090227.xyz"
    - "+.090227.xyz"
    - "cloudflare.182682.xyz"
    - "+.182682.xyz"
    - "+.trycloudflare.com"
    - "+.cloudflare.com"
rules:
  - GEOIP,Private,DIRECT
  - MATCH,Proxy
`

const ProxyGroups = `- name: Proxy
  type: select
  proxies: []
- name: Auto
  type: url-test
  proxies: []
  url: http://www.gstatic.com/generate_204
  interval: 300
  tolerance: 50
- name: 优选
  type: url-test
  proxies: []
  url: http://www.gstatic.com/generate_204
  interval: 300
  tolerance: 50
`

func (s *ClashService) GetClash(subId string) (*string, []string, error) {

	client, inDatas, err := s.getData(subId)
	if err != nil {
		return nil, nil, err
	}

	outbounds, outTags, err := s.getOutbounds(client.Config, inDatas)
	if err != nil {
		return nil, nil, err
	}

	links := s.LinkService.GetLinks(&client.Links, "external", "")
	for _, link := range links {
		json, tag, err := util.GetOutbound(link, 0)
		if err == nil && len(tag) > 0 {
			*outbounds = append(*outbounds, *json)
			*outTags = append(*outTags, tag)
		}
	}

	basicConfig, err := s.getClashConfig()
	if err != nil || len(basicConfig) == 0 {
		basicConfig = basicClashConfig
	}

	resultStr, err := s.ConvertToClashMeta(outbounds, basicConfig)
	if err != nil {
		return nil, nil, err
	}

	updateInterval, _ := s.SettingService.GetSubUpdates()
	headers := util.GetHeaders(client, updateInterval)

	return &resultStr, headers, nil
}

func (s *ClashService) getClashConfig() (string, error) {
	subClashExt, err := s.SettingService.GetSubClashExt()
	if err != nil {
		return "", err
	}
	ext := strings.TrimSpace(subClashExt)
	if ext == "" {
		return basicClashConfig, nil
	}
	// Shallow-merge user overlay onto built-in template so a rules-only editor
	// does not wipe dns/tun/mixed-port from the default Clash base.
	var base map[string]interface{}
	if err := yaml.Unmarshal([]byte(basicClashConfig), &base); err != nil || base == nil {
		return ext, nil
	}
	var overlay map[string]interface{}
	if err := yaml.Unmarshal([]byte(ext), &overlay); err != nil || overlay == nil {
		return basicClashConfig, nil
	}
	for k, v := range overlay {
		base[k] = v
	}
	out, err := yaml.Marshal(base)
	if err != nil {
		return basicClashConfig, nil
	}
	return string(out), nil
}

// injectPanelBypass makes panel traffic follow the selected Proxy node (not DIRECT).
// Mainland paths often cannot open the raw panel IP:port; the node path plus server
// hairpin NAT is what actually works. Domain/IP come from webDomain at sub time.
func (s *ClashService) injectPanelBypass(output map[string]interface{}) {
	if output == nil {
		return
	}
	domain, _ := s.GetWebDomain()
	domain = strings.TrimSpace(strings.ToLower(domain))
	stripped := []string{}
	injected := []string{}
	resolvedIPs := []string{}
	if domain == "" {
		return
	}

	if ips, err := net.LookupIP(domain); err == nil {
		seen := map[string]struct{}{}
		for _, ip := range ips {
			v4 := ip.To4()
			if v4 == nil {
				continue
			}
			sIP := v4.String()
			if _, ok := seen[sIP]; ok {
				continue
			}
			seen[sIP] = struct{}{}
			resolvedIPs = append(resolvedIPs, sIP)
		}
	}

	existing := []string{}
	switch r := output["rules"].(type) {
	case []interface{}:
		for _, item := range r {
			if s, ok := item.(string); ok {
				existing = append(existing, s)
			}
		}
	case []string:
		existing = append(existing, r...)
	}

	// Drop any prior panel DIRECT rules (v1.6.4 era) so panel can use the node.
	filtered := make([]string, 0, len(existing))
	for _, e := range existing {
		compact := strings.ReplaceAll(e, " ", "")
		drop := false
		if strings.Contains(compact, ",DIRECT") {
			if strings.Contains(compact, "DOMAIN,"+domain+",") ||
				strings.Contains(compact, "DOMAIN-SUFFIX,"+domain+",") {
				drop = true
			}
			for _, ip := range resolvedIPs {
				if strings.Contains(compact, "IP-CIDR,"+ip+"/") {
					drop = true
					break
				}
			}
		}
		if drop {
			stripped = append(stripped, e)
			continue
		}
		filtered = append(filtered, e)
	}

	want := []string{
		fmt.Sprintf("DOMAIN,%s,Proxy", domain),
	}
	for _, ip := range resolvedIPs {
		want = append(want, fmt.Sprintf("IP-CIDR,%s/32,Proxy,no-resolve", ip))
	}
	have := map[string]struct{}{}
	for _, e := range filtered {
		have[strings.ReplaceAll(e, " ", "")] = struct{}{}
	}
	pre := make([]string, 0, len(want))
	for _, w := range want {
		key := strings.ReplaceAll(w, " ", "")
		if _, ok := have[key]; ok {
			continue
		}
		pre = append(pre, w)
		injected = append(injected, w)
	}
	merged := make([]interface{}, 0, len(pre)+len(filtered))
	for _, p := range pre {
		merged = append(merged, p)
	}
	for _, e := range filtered {
		merged = append(merged, e)
	}
	output["rules"] = merged

	// DoH for panel host (ISP DNS may poison it); keep fake-ip so TUN sniff works.
	dnsMap, _ := output["dns"].(map[string]interface{})
	if dnsMap == nil {
		dnsMap = map[string]interface{}{}
	}
	policy, _ := dnsMap["nameserver-policy"].(map[string]interface{})
	if policy == nil {
		policy = map[string]interface{}{}
	}
	if _, ok := policy[domain]; !ok {
		policy[domain] = []interface{}{
			"https://1.1.1.1/dns-query",
			"https://dns.google/dns-query",
		}
		dnsMap["nameserver-policy"] = policy
	}
	output["dns"] = dnsMap

	if _, ok := output["sniffer"]; !ok {
		output["sniffer"] = map[string]interface{}{
			"enable":               true,
			"override-destination": true,
			"sniff": map[string]interface{}{
				"TLS": map[string]interface{}{
					"ports": []interface{}{443, 8443, 2095, 2096},
				},
				"HTTP": map[string]interface{}{
					"ports": []interface{}{80, 8080, 8880, 2052, 2082, 2086, 2095},
				},
			},
		}
	}
}

func (s *ClashService) ConvertToClashMeta(outbounds *[]map[string]interface{}, basicConfig string) (string, error) {
	var proxies []interface{}
	proxyTags := make([]string, 0)
	for _, obMap := range *outbounds {

		t, _ := obMap["type"].(string)
		if t == "selector" || t == "urltest" || t == "direct" {
			continue
		}

		proxy := make(map[string]interface{})
		proxy["name"] = obMap["tag"]
		proxy["type"] = t

		server, _ := obMap["server"].(string)
		if len(server) > 0 && strings.Contains(server, ":") && !strings.Contains(server, ".") && !(strings.HasPrefix(server, "[") && strings.HasSuffix(server, "]")) {
			server = "'[" + server + "]'"
		}
		proxy["server"] = server

		proxy["port"] = obMap["server_port"]

		switch t {
		case "vmess", "vless", "tuic":
			proxy["uuid"] = obMap["uuid"]
			if t == "vmess" {
				if alterId, ok := obMap["alter_id"].(float64); ok {
					proxy["alterId"] = int(alterId)
				} else {
					proxy["alterId"] = 0
				}
				proxy["cipher"] = "auto"
			}
			if t == "vless" {
				if flow, ok := obMap["flow"].(string); ok && flow != "" {
					proxy["flow"] = flow
				}
			}
			if t == "tuic" {
				proxy["password"] = obMap["password"]
				if congestion_control, ok := obMap["congestion_control"].(string); ok {
					proxy["congestion-controller"] = congestion_control
				}
				proxy["udp"] = true
				proxy["udp-relay-mode"] = "native"
			}
		case "trojan":
			proxy["password"] = obMap["password"]
		case "socks", "http":
			if t == "socks" {
				proxy["type"] = "socks5"
			}
			proxy["username"] = obMap["username"]
			proxy["password"] = obMap["password"]
		case "hysteria", "hysteria2":
			if _, ok := obMap["up_mbps"].(float64); ok {
				proxy["up"] = obMap["up_mbps"]
			}
			if _, ok := obMap["down_mbps"].(float64); ok {
				proxy["down"] = obMap["down_mbps"]
			}
			if t == "hysteria" {
				proxy["auth-str"] = obMap["auth_str"]
				if obfs, ok := obMap["obfs"].(string); ok {
					proxy["obfs"] = obfs
				}
			} else {
				proxy["password"] = obMap["password"]
				if obfs, ok := obMap["obfs"].(map[string]interface{}); ok {
					proxy["obfs"] = obfs["type"]
					proxy["obfs-password"] = obfs["password"]
				}
			}

			if portLists, ok := obMap["server_ports"].([]interface{}); ok {
				var ports []string
				for _, portList := range portLists {
					portRange, _ := portList.(string)
					ports = append(ports, strings.ReplaceAll(portRange, ":", "-"))
				}
				proxy["ports"] = strings.Join(ports, ",")
			}
		case "anytls":
			proxy["password"] = obMap["password"]
			if tls, ok := obMap["tls"].(map[string]interface{}); ok {
				proxy["sni"] = tls["server_name"]
				proxy["skip-cert-verify"] = tls["insecure"]
			}
		case "shadowsocks":
			proxy["type"] = "ss"
			proxy["cipher"] = obMap["method"]
			proxy["password"] = obMap["password"]
			if network, ok := obMap["network"].(string); ok && network != "tcp" {
				proxy["udp"] = true
			}
			if uot, ok := obMap["udp_over_tcp"].(bool); ok && uot {
				proxy["udp-over-tcp"] = true
			}
		default:
			continue
		}

		// TLS params
		tls, isTls := obMap["tls"].(map[string]interface{})
		if isTls {
			tlsEnabled, ok := tls["enabled"].(bool)
			if ok && !tlsEnabled {
				isTls = false
			}
		}
		if isTls {
			// tuic/hysteria already imply TLS; a bare tls:true field can confuse some Clash Meta builds.
			if t != "tuic" && t != "hysteria" && t != "hysteria2" && t != "anytls" {
				proxy["tls"] = tls["enabled"]
			}

			// ALPN if exists. TUIC is QUIC — only h3 is valid; h2/http1.1 breaks some clients.
			if alpn, ok := tls["alpn"].([]interface{}); ok {
				if t == "tuic" {
					proxy["alpn"] = []string{"h3"}
				} else {
					proxy["alpn"] = alpn
				}
			} else if t == "tuic" {
				proxy["alpn"] = []string{"h3"}
			}

			// Add reality if exists
			if reality, ok := tls["reality"].(map[string]interface{}); ok && reality["enabled"].(bool) {
				reality_opts := make(map[string]interface{})
				if pbk, ok := reality["public_key"].(string); ok {
					reality_opts["public-key"] = pbk
				}
				if sid, ok := reality["short_id"].(string); ok {
					reality_opts["short-id"] = sid
				}
				proxy["reality-opts"] = reality_opts
			}
			if utls, ok := tls["utls"].(map[string]interface{}); ok {
				if enabled, ok := utls["enabled"].(bool); ok && enabled {
					if fp, ok := utls["fingerprint"].(string); ok {
						proxy["client-fingerprint"] = fp
					}
				}
			}
			if sni, ok := tls["server_name"].(string); ok {
				if t == "vless" || t == "vmess" {
					proxy["servername"] = sni
				} else {
					proxy["sni"] = sni
				}
			}
			if insecure, ok := tls["insecure"].(bool); ok && insecure {
				proxy["skip-cert-verify"] = insecure
			}
			// ech outbounds
			if ech, ok := tls["ech"].(map[string]interface{}); ok && ech["enabled"].(bool) {
				ech_config, _ := ech["config"].([]interface{})
				ech_string := ""
				for i := 1; i < len(ech_config)-1; i++ {
					ech_string += ech_config[i].(string)
				}
				proxy["ech-opts"] = map[string]interface{}{
					"enable": true,
					"config": ech_string,
				}
			}
		}

		// Transport if exist
		if transport, ok := obMap["transport"].(map[string]interface{}); ok {
			tt, _ := transport["type"].(string)
			switch tt {
			case "http":
				httpOpts := make(map[string]interface{})
				if path, ok := transport["path"].([]interface{}); ok {
					httpOpts["path"] = path[0]
				} else if path, ok := transport["path"].(string); ok {
					httpOpts["path"] = path
				}
				if host, ok := transport["host"].([]interface{}); ok {
					httpOpts["host"] = host[0]
				}
				if isTls {
					proxy["network"] = "h2"
					proxy["h2-opts"] = httpOpts
				} else {
					proxy["network"] = "http"
					proxy["http-opts"] = map[string]interface{}{"path": []interface{}{httpOpts["path"]}, "host": httpOpts["host"]}
				}
			case "ws", "httpupgrade":
				proxy["network"] = "ws"
				wsOpts := make(map[string]interface{})
				if path, ok := transport["path"].(string); ok {
					wsOpts["path"] = path
				}
				// sing-box/S-UI stores headers as object {"Host": "..."} (suoha prefer needs this);
				// some configs use a list — accept both so Clash Meta keeps Host.
				hostHeader := ""
				if headers, ok := transport["headers"].([]interface{}); ok {
					wsOpts["headers"] = headers
				} else if headers, ok := transport["headers"].(map[string]interface{}); ok {
					wsOpts["headers"] = headers
					if h, ok := headers["Host"].(string); ok {
						hostHeader = h
					} else if h, ok := headers["host"].(string); ok {
						hostHeader = h
					}
				}
				// CDN prefer (优选1/2): server is cf.090227.xyz / cloudflare.182682.xyz while
				// tunnel Host/SNI must stay on the Argo hostname. Without ws-opts.headers.Host,
				// many VLESS clients send Host=<server> and the node fails; 默认 works because
				// server already equals the Argo hostname.
				if hostHeader == "" {
					if tls, ok := obMap["tls"].(map[string]interface{}); ok {
						if sni, ok := tls["server_name"].(string); ok && sni != "" {
							hostHeader = sni
						}
					}
				}
				if hostHeader == "" {
					if sni, ok := proxy["servername"].(string); ok && sni != "" {
						hostHeader = sni
					} else if sni, ok := proxy["sni"].(string); ok && sni != "" {
						hostHeader = sni
					}
				}
				if hostHeader != "" {
					wsOpts["headers"] = map[string]interface{}{"Host": hostHeader}
				}
				if ed, ok := transport["early_data_header_name"].(string); ok {
					wsOpts["early-data-header-name"] = ed
				}
				if tt == "httpupgrade" {
					wsOpts["v2ray-http-upgrade"] = true
				}
				proxy["ws-opts"] = wsOpts
			case "grpc":
				proxy["network"] = "grpc"
				grpcOpts := make(map[string]interface{})
				if service_name, ok := transport["service_name"].(string); ok {
					grpcOpts["grpc-service-name"] = service_name
				}
				proxy["grpc-opts"] = grpcOpts
			}
		}

		// Multiplex
		if mux, ok := obMap["multiplex"].(map[string]interface{}); ok {
			if enabled, ok := mux["enabled"].(bool); ok && enabled {
				smux := make(map[string]interface{})
				smux["enabled"] = true
				if protocol, ok := mux["protocol"].(string); ok {
					smux["protocol"] = protocol
				}
				if _, ok := mux["max_connections"].(float64); ok {
					smux["max-connections"] = mux["max_connections"]
				}
				if _, ok := mux["min_streams"].(float64); ok {
					smux["min-streams"] = mux["min_streams"]
				}
				if _, ok := mux["max_streams"].(float64); ok {
					smux["max-streams"] = mux["max_streams"]
				}
				if _, ok := mux["padding"].(bool); ok {
					smux["padding"] = mux["padding"]
				}
				if brutal, ok := mux["brutal"].(map[string]interface{}); ok {
					if enabled, ok := brutal["enabled"].(bool); ok && enabled {
						brutalOpts := make(map[string]interface{})
						brutalOpts["enabled"] = true
						if _, ok := brutal["up_mbps"].(float64); ok {
							brutalOpts["up"] = brutal["up_mbps"]
						}
						if _, ok := brutal["down_mbps"].(float64); ok {
							brutalOpts["down"] = brutal["down_mbps"]
						}
						smux["brutal-opts"] = brutalOpts
					}
				}
				proxy["smux"] = smux
			}
		}

		proxies = append(proxies, proxy)
		proxyTags = append(proxyTags, obMap["tag"].(string))
	}

	// B: order tags — 优选1..N before 默认(Argo直连入口); keep TUD after prefer for Auto/Proxy lists
	proxyTags = sortProxyTagsPreferFirst(proxyTags)
	preferOnlyTags := filterPreferProxyTags(proxyTags)

	var proxyGroups []map[string]interface{}
	err := yaml.Unmarshal([]byte(ProxyGroups), &proxyGroups)
	if err != nil {
		logger.Error(err.Error())
	}

	proxyGroups[1]["proxies"] = proxyTags // Auto = all nodes this client checked
	// Only emit「优选」group when this client actually has prefer nodes.
	// Previously empty prefer fell back to ALL tags, so TUD-only users still saw「优选」.
	var outGroups []interface{}
	if len(preferOnlyTags) > 0 {
		proxyGroups[2]["proxies"] = preferOnlyTags
		proxyGroups[0]["proxies"] = append(
			[]string{proxyGroups[1]["name"].(string), proxyGroups[2]["name"].(string)},
			proxyTags...,
		)
		outGroups = []interface{}{proxyGroups[0], proxyGroups[1], proxyGroups[2]}
	} else {
		proxyGroups[0]["proxies"] = append(
			[]string{proxyGroups[1]["name"].(string)},
			proxyTags...,
		)
		outGroups = []interface{}{proxyGroups[0], proxyGroups[1]}
	}

	// Merge proxies and proxy groups if exist
	var output map[string]interface{}
	err = yaml.Unmarshal([]byte(basicConfig), &output)
	if err != nil {
		logger.Error(err.Error())
	}

	if p, ok := output["proxies"].([]interface{}); ok {
		output["proxies"] = append(p, proxies...)
	} else {
		output["proxies"] = proxies
	}

	if pg, ok := output["proxy-groups"].([]interface{}); ok {
		output["proxy-groups"] = append(pg, outGroups...)
	} else {
		output["proxy-groups"] = outGroups
	}

	s.injectPanelBypass(output)

	result, err := yaml.Marshal(output)
	if err != nil {
		return "", err
	}
	return string(result), nil
}

// sortProxyTagsPreferFirst puts 优选1..4 before 默认(Argo hostname entry), then TUD.
func sortProxyTagsPreferFirst(tags []string) []string {
	var p1, p2, p3, p4, pDef, tud, other []string
	for _, t := range tags {
		switch {
		case strings.Contains(t, "优选1"):
			p1 = append(p1, t)
		case strings.Contains(t, "优选2"):
			p2 = append(p2, t)
		case strings.Contains(t, "优选3"):
			p3 = append(p3, t)
		case strings.Contains(t, "优选4"):
			p4 = append(p4, t)
		case strings.Contains(t, "优选") && strings.Contains(t, "默认"):
			pDef = append(pDef, t)
		case strings.Contains(t, "-TUD-"):
			tud = append(tud, t)
		default:
			other = append(other, t)
		}
	}
	out := make([]string, 0, len(tags))
	out = append(out, p1...)
	out = append(out, p2...)
	out = append(out, p3...)
	out = append(out, p4...)
	out = append(out, pDef...)
	out = append(out, tud...)
	out = append(out, other...)
	return out
}

func filterPreferProxyTags(tags []string) []string {
	out := make([]string, 0, len(tags))
	for _, t := range tags {
		if strings.Contains(t, "优选") && !strings.Contains(t, "-TUD-") {
			out = append(out, t)
		}
	}
	return out
}
