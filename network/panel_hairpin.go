package network

import (
	"fmt"
	"net"
	"os/exec"
	"strconv"
	"strings"
)

// EnsurePanelHairpin DNAT's local dials to the panel's public IPv4:port back to
// 127.0.0.1:port. Without this, traffic that reaches this host via a node and
// then dials the panel public address fails (no hairpin), which shows up on
// clients as ERR_CONNECTION_CLOSED.
func EnsurePanelHairpin(domain string, port int) {
	domain = strings.TrimSpace(strings.ToLower(domain))
	if port <= 0 || port > 65535 {
		return
	}
	ips := map[string]struct{}{}
	if domain != "" {
		if resolved, err := net.LookupIP(domain); err == nil {
			for _, ip := range resolved {
				if v4 := ip.To4(); v4 != nil {
					ips[v4.String()] = struct{}{}
				}
			}
		}
	}
	// Also cover primary interface addresses so DDNS lag still works.
	if ifaces, err := net.InterfaceAddrs(); err == nil {
		for _, a := range ifaces {
			ipNet, ok := a.(*net.IPNet)
			if !ok || ipNet.IP == nil {
				continue
			}
			v4 := ipNet.IP.To4()
			if v4 == nil || v4.IsLoopback() || v4.IsPrivate() || v4.IsLinkLocalUnicast() {
				continue
			}
			ips[v4.String()] = struct{}{}
		}
	}
	portStr := strconv.Itoa(port)
	dest := "127.0.0.1:" + portStr
	for ip := range ips {
		spec := []string{
			"-t", "nat", "-d", ip + "/32", "-p", "tcp",
			"--dport", portStr, "-j", "DNAT", "--to-destination", dest,
		}
		_ = iptablesEnsure("OUTPUT", spec)
	}
}

func iptablesEnsure(chain string, spec []string) error {
	check := append([]string{"-C", chain}, spec...)
	if err := exec.Command("iptables", check...).Run(); err == nil {
		return nil
	}
	insert := append([]string{"-I", chain}, spec...)
	out, err := exec.Command("iptables", insert...).CombinedOutput()
	if err != nil {
		return fmt.Errorf("%v: %s", err, strings.TrimSpace(string(out)))
	}
	return nil
}
