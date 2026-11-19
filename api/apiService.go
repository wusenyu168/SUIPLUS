package api

import (
	"context"
	"encoding/json"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/admin8800/s-ui/database"
	"github.com/admin8800/s-ui/logger"
	"github.com/admin8800/s-ui/service"
	"github.com/admin8800/s-ui/util"
	"github.com/admin8800/s-ui/util/common"

	"github.com/gin-gonic/gin"
)

type ApiService struct {
	service.SettingService
	service.UserService
	service.ConfigService
	service.ClientService
	service.TlsService
	service.InboundService
	service.OutboundService
	service.EndpointService
	service.ServicesService
	service.PanelService
	service.StatsService
	service.ServerService
}

func (a *ApiService) LoadData(c *gin.Context) {
	data, err := a.getData(c)
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	jsonObj(c, data, nil)
}

func (a *ApiService) getData(c *gin.Context) (interface{}, error) {
	data := make(map[string]interface{}, 0)
	lu := c.Query("lu")
	isUpdated, err := a.ConfigService.CheckChanges(lu)
	if err != nil {
		return "", err
	}
	onlines, err := a.StatsService.GetOnlines()

	sysInfo := a.ServerService.GetSingboxInfo()
	if sysInfo["running"] == false {
		logs := a.ServerService.GetLogs("1", "debug")
		if len(logs) > 0 {
			data["lastLog"] = logs[0]
		}
	}

	if err != nil {
		return "", err
	}
	if isUpdated {
		config, err := a.SettingService.GetConfig()
		if err != nil {
			return "", err
		}
		clients, err := a.ClientService.GetAll()
		if err != nil {
			return "", err
		}
		tlsConfigs, err := a.TlsService.GetAll()
		if err != nil {
			return "", err
		}
		inbounds, err := a.InboundService.GetAll()
		if err != nil {
			return "", err
		}
		outbounds, err := a.OutboundService.GetAll()
		if err != nil {
			return "", err
		}
		endpoints, err := a.EndpointService.GetAll()
		if err != nil {
			return "", err
		}
		services, err := a.ServicesService.GetAll()
		if err != nil {
			return "", err
		}
		subURI, err := a.SettingService.GetFinalSubURI(getHostname(c))
		if err != nil {
			return "", err
		}
		trafficAge, err := a.SettingService.GetTrafficAge()
		if err != nil {
			return "", err
		}
		data["config"] = json.RawMessage(config)
		data["clients"] = clients
		data["tls"] = tlsConfigs
		data["inbounds"] = inbounds
		data["outbounds"] = outbounds
		data["endpoints"] = endpoints
		data["services"] = services
		data["subURI"] = subURI
		data["enableTraffic"] = trafficAge > 0
		data["onlines"] = onlines
	} else {
		data["onlines"] = onlines
	}

	return data, nil
}

func (a *ApiService) LoadPartialData(c *gin.Context, objs []string) error {
	data := make(map[string]interface{}, 0)
	id := c.Query("id")

	for _, obj := range objs {
		switch obj {
		case "inbounds":
			inbounds, err := a.InboundService.Get(id)
			if err != nil {
				return err
			}
			data[obj] = inbounds
		case "outbounds":
			outbounds, err := a.OutboundService.GetAll()
			if err != nil {
				return err
			}
			data[obj] = outbounds
		case "endpoints":
			endpoints, err := a.EndpointService.GetAll()
			if err != nil {
				return err
			}
			data[obj] = endpoints
		case "services":
			services, err := a.ServicesService.GetAll()
			if err != nil {
				return err
			}
			data[obj] = services
		case "tls":
			tlsConfigs, err := a.TlsService.GetAll()
			if err != nil {
				return err
			}
			data[obj] = tlsConfigs
		case "clients":
			clients, err := a.ClientService.Get(id)
			if err != nil {
				return err
			}
			data[obj] = clients
		case "config":
			config, err := a.SettingService.GetConfig()
			if err != nil {
				return err
			}
			data[obj] = json.RawMessage(config)
		case "settings":
			settings, err := a.SettingService.GetAllSetting()
			if err != nil {
				return err
			}
			data[obj] = settings
		}
	}

	jsonObj(c, data, nil)
	return nil
}

func (a *ApiService) GetUsers(c *gin.Context) {
	users, err := a.UserService.GetUsers()
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	jsonObj(c, *users, nil)
}

func (a *ApiService) GetSettings(c *gin.Context) {
	data, err := a.SettingService.GetAllSetting()
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	jsonObj(c, data, err)
}

func (a *ApiService) GetStats(c *gin.Context) {
	resource := c.Query("resource")
	tag := c.Query("tag")
	limit, err := strconv.Atoi(c.Query("limit"))
	if err != nil {
		limit = 100
	}
	data, err := a.StatsService.GetStats(resource, tag, limit)
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	jsonObj(c, data, err)
}

func (a *ApiService) GetStatus(c *gin.Context) {
	request := c.Query("r")
	result := a.ServerService.GetStatus(request)
	jsonObj(c, result, nil)
}

func (a *ApiService) GetOnlines(c *gin.Context) {
	onlines, err := a.StatsService.GetOnlines()
	jsonObj(c, onlines, err)
}

func (a *ApiService) GetLogs(c *gin.Context) {
	count := c.Query("c")
	level := c.Query("l")
	logs := a.ServerService.GetLogs(count, level)
	jsonObj(c, logs, nil)
}

func (a *ApiService) CheckChanges(c *gin.Context) {
	actor := c.Query("a")
	chngKey := c.Query("k")
	count := c.Query("c")
	changes := a.ConfigService.GetChanges(actor, chngKey, count)
	jsonObj(c, changes, nil)
}

func (a *ApiService) GetKeypairs(c *gin.Context) {
	kType := c.Query("k")
	options := c.Query("o")
	keypair := a.ServerService.GenKeypair(kType, options)
	jsonObj(c, keypair, nil)
}

func (a *ApiService) GetDb(c *gin.Context) {
	exclude := c.Query("exclude")
	db, err := database.GetDb(exclude)
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	c.Header("Content-Type", "application/octet-stream")
	c.Header("Content-Disposition", "attachment; filename=s-ui_"+time.Now().Format("20060102-150405")+".db")
	c.Writer.Write(db)
}

func (a *ApiService) postActions(c *gin.Context) (string, json.RawMessage, error) {
	var data map[string]json.RawMessage
	err := c.ShouldBind(&data)
	if err != nil {
		return "", nil, err
	}
	return string(data["action"]), data["data"], nil
}

func (a *ApiService) Login(c *gin.Context) {
	remoteIP := getRemoteIp(c)
	loginUser, err := a.UserService.Login(c.Request.FormValue("user"), c.Request.FormValue("pass"), remoteIP)
	if err != nil {
		jsonMsg(c, "", err)
		return
	}

	sessionMaxAge, err := a.SettingService.GetSessionMaxAge()
	if err != nil {
		logger.Infof("Unable to get session's max age from DB")
	}

	err = SetLoginUser(c, loginUser, sessionMaxAge)
	if err == nil {
		logger.Info("user ", loginUser, " login success")
	} else {
		logger.Warning("login failed: ", err)
	}

	jsonMsg(c, "", nil)
}

func (a *ApiService) ChangePass(c *gin.Context) {
	id := c.Request.FormValue("id")
	oldPass := c.Request.FormValue("oldPass")
	newUsername := c.Request.FormValue("newUsername")
	newPass := c.Request.FormValue("newPass")
	err := a.UserService.ChangePass(id, oldPass, newUsername, newPass)
	if err == nil {
		logger.Info("change user credentials success")
		jsonMsg(c, "save", nil)
	} else {
		logger.Warning("change user credentials failed:", err)
		jsonMsg(c, "", err)
	}
}

func (a *ApiService) Save(c *gin.Context, loginUser string) {
	hostname := getHostname(c)
	obj := c.Request.FormValue("object")
	act := c.Request.FormValue("action")
	data := c.Request.FormValue("data")
	initUsers := c.Request.FormValue("initUsers")
	objs, err := a.ConfigService.Save(obj, act, json.RawMessage(data), initUsers, loginUser, hostname)
	if err != nil {
		jsonMsg(c, "save", err)
		return
	}
	// Settings save: apply DDNS interval + TUD addrs + prefer (prefer separated from DDNS timer)
	if obj == "settings" {
		go func() {
			script := "/usr/local/s-ui/scripts/suiplus_after_settings.py"
			if err := exec.Command("python3", script).Run(); err != nil {
				_ = exec.Command("python3", "/usr/local/s-ui/scripts/suiplus_sync_addrs.py").Run()
				_ = exec.Command("python3", "/usr/local/s-ui/scripts/suiplus_sync_prefer.py").Run()
				_ = exec.Command("python3", "/usr/local/s-ui/scripts/suiplus_apply_ddns_timer.py").Run()
			}
		}()
	}
	err = a.LoadPartialData(c, objs)
	if err != nil {
		jsonMsg(c, obj, err)
	}
}

func (a *ApiService) RestartApp(c *gin.Context) {
	// Must be seconds: RestartPanel(3) is 3ns in Go and drops the HTTP response → Axios Network Error
	err := a.PanelService.RestartPanel(3 * time.Second)
	jsonMsg(c, "restartApp", err)
}

func (a *ApiService) IssueCert(c *gin.Context) {
	script := "/usr/local/s-ui/scripts/suiplus_issue_cert.sh"
	out, err := exec.Command("bash", script).CombinedOutput()
	if err != nil {
		jsonMsg(c, "issueCert", common.NewError(string(out), " | ", err.Error()))
		return
	}
	// Prefer fresh values from DB (script upserts webDomain + cert paths)
	all, _ := a.SettingService.GetAllSetting()
	result := map[string]string{}
	if all != nil {
		for _, k := range []string{"webDomain", "subDomain", "webCertFile", "webKeyFile", "subCertFile", "subKeyFile"} {
			if v, ok := (*all)[k]; ok {
				result[k] = v
			}
		}
	}
	// Fallback parse SUIPLUS_CERT_RESULT line
	if result["webCertFile"] == "" {
		for _, line := range strings.Split(string(out), "\n") {
			if !strings.HasPrefix(line, "SUIPLUS_CERT_RESULT ") {
				continue
			}
			for _, part := range strings.Fields(strings.TrimPrefix(line, "SUIPLUS_CERT_RESULT ")) {
				kv := strings.SplitN(part, "=", 2)
				if len(kv) != 2 {
					continue
				}
				switch kv[0] {
				case "domain":
					result["webDomain"] = kv[1]
					result["subDomain"] = kv[1]
				case "cert":
					result["webCertFile"] = kv[1]
					result["subCertFile"] = kv[1]
				case "key":
					result["webKeyFile"] = kv[1]
					result["subKeyFile"] = kv[1]
				}
			}
		}
	}
	_ = exec.Command("python3", "/usr/local/s-ui/scripts/suiplus_after_settings.py").Run()
	jsonMsgObj(c, "issueCert", result, nil)
}

func parseScriptJSON(text string) map[string]interface{} {
	var payload map[string]interface{}
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "{") && strings.Contains(line, "\"ok\"") {
			_ = json.Unmarshal([]byte(line), &payload)
		}
	}
	return payload
}

func pppoeResultFromPayload(payload map[string]interface{}, msg string) map[string]string {
	result := map[string]string{}
	for _, k := range []string{
		"pppoePrevIp", "pppoeLastIp", "pppoeLastAt", "pppoeLastSuccessTs", "pppoePending",
		"prev_ip", "last_ip", "last_at", "argoDomain", "argoLastRebuildTs",
	} {
		if v, ok := payload[k].(string); ok {
			result[k] = v
		}
	}
	if result["pppoePrevIp"] == "" {
		result["pppoePrevIp"] = result["prev_ip"]
	}
	if result["pppoeLastIp"] == "" {
		result["pppoeLastIp"] = result["last_ip"]
	}
	if result["pppoeLastAt"] == "" {
		result["pppoeLastAt"] = result["last_at"]
	}
	if msg != "" {
		result["message"] = msg
	}
	return result
}

func (a *ApiService) PppoeRedial(c *gin.Context) {
	script := "/usr/local/s-ui/scripts/suiplus_pppoe_redial.py"
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	out, err := exec.CommandContext(ctx, "python3", script).CombinedOutput()
	text := strings.TrimSpace(string(out))
	if ctx.Err() == context.DeadlineExceeded {
		jsonMsg(c, "pppoeRedial", common.NewError("重拨超时，请稍后点「获取 IP」或查看 /var/log/suiplus-pppoe.log"))
		return
	}
	payload := parseScriptJSON(text)
	if payload == nil {
		if err != nil {
			jsonMsg(c, "pppoeRedial", common.NewError(text, " | ", err.Error()))
			return
		}
		jsonMsg(c, "pppoeRedial", common.NewError(text))
		return
	}
	ok, _ := payload["ok"].(bool)
	msg, _ := payload["msg"].(string)
	result := pppoeResultFromPayload(payload, msg)
	if !ok {
		if msg == "" {
			msg = "重拨失败"
		}
		// Still return partial IPs so UI can refresh prev/pending
		jsonMsgObj(c, "pppoeRedial", result, common.NewError(msg))
		return
	}
	jsonObj(c, result, nil)
}

func (a *ApiService) PppoeShowIp(c *gin.Context) {
	script := "/usr/local/s-ui/scripts/suiplus_pppoe_redial.py"
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, "python3", script, "--showip").CombinedOutput()
	text := strings.TrimSpace(string(out))
	if ctx.Err() == context.DeadlineExceeded {
		jsonMsg(c, "pppoeShowIp", common.NewError("获取 IP 超时，请稍后重试"))
		return
	}
	payload := parseScriptJSON(text)
	if payload == nil {
		if err != nil {
			jsonMsg(c, "pppoeShowIp", common.NewError(text, " | ", err.Error()))
			return
		}
		jsonMsg(c, "pppoeShowIp", common.NewError(text))
		return
	}
	ok, _ := payload["ok"].(bool)
	msg, _ := payload["msg"].(string)
	result := pppoeResultFromPayload(payload, msg)
	if !ok {
		if msg == "" {
			msg = "获取 IP 失败"
		}
		jsonMsgObj(c, "pppoeShowIp", result, common.NewError(msg))
		return
	}
	jsonObj(c, result, nil)
}

func (a *ApiService) ArgoRebuild(c *gin.Context) {
	script := "/usr/local/s-ui/scripts/suiplus_argo_health.py"
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	out, err := exec.CommandContext(ctx, "python3", script, "--force").CombinedOutput()
	text := strings.TrimSpace(string(out))
	if ctx.Err() == context.DeadlineExceeded {
		jsonMsg(c, "argoRebuild", common.NewError("重建超时，请查看 /var/log/suiplus-argo-health.log"))
		return
	}
	payload := parseScriptJSON(text)
	if payload == nil {
		if err != nil {
			jsonMsg(c, "argoRebuild", common.NewError(text, " | ", err.Error()))
			return
		}
		jsonMsg(c, "argoRebuild", common.NewError(text))
		return
	}
	ok, _ := payload["ok"].(bool)
	msg, _ := payload["msg"].(string)
	result := pppoeResultFromPayload(payload, msg)
	if !ok {
		if msg == "" {
			msg = "Argo 重建失败"
		}
		jsonMsg(c, "argoRebuild", common.NewError(msg))
		return
	}
	jsonObj(c, result, nil)
}

func (a *ApiService) RestartSb(c *gin.Context) {
	err := a.ConfigService.RestartCore()
	jsonMsg(c, "restartSb", err)
}

func (a *ApiService) LinkConvert(c *gin.Context) {
	link := c.Request.FormValue("link")
	result, _, err := util.GetOutbound(link, 0)
	jsonObj(c, result, err)
}

func (a *ApiService) SubConvert(c *gin.Context) {
	link := c.Request.FormValue("link")
	result, err := util.GetExternalSub(link)
	jsonObj(c, result, err)
}

func (a *ApiService) ImportDb(c *gin.Context) {
	file, _, err := c.Request.FormFile("db")
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	defer file.Close()
	err = database.ImportDB(file)
	jsonMsg(c, "", err)
}

func (a *ApiService) Logout(c *gin.Context) {
	loginUser := GetLoginUser(c)
	if loginUser != "" {
		logger.Infof("user %s logout", loginUser)
	}
	ClearSession(c)
	jsonMsg(c, "", nil)
}

func (a *ApiService) LoadTokens() ([]byte, error) {
	return a.UserService.LoadTokens()
}

func (a *ApiService) GetTokens(c *gin.Context) {
	loginUser := GetLoginUser(c)
	tokens, err := a.UserService.GetUserTokens(loginUser)
	jsonObj(c, tokens, err)
}

func (a *ApiService) AddToken(c *gin.Context) {
	loginUser := GetLoginUser(c)
	expiry := c.Request.FormValue("expiry")
	expiryInt, err := strconv.ParseInt(expiry, 10, 64)
	if err != nil {
		jsonMsg(c, "", err)
		return
	}
	desc := c.Request.FormValue("desc")
	token, err := a.UserService.AddToken(loginUser, expiryInt, desc)
	jsonObj(c, token, err)
}

func (a *ApiService) DeleteToken(c *gin.Context) {
	tokenId := c.Request.FormValue("id")
	err := a.UserService.DeleteToken(tokenId)
	jsonMsg(c, "", err)
}

func (a *ApiService) GetSingboxConfig(c *gin.Context) {
	rawConfig, err := a.ConfigService.GetConfig("")
	if err != nil {
		c.Status(400)
		c.Writer.WriteString(err.Error())
		return
	}
	c.Header("Content-Type", "application/json")
	c.Header("Content-Disposition", "attachment; filename=config_"+time.Now().Format("20060102-150405")+".json")
	c.Writer.Write(*rawConfig)
}

func (a *ApiService) GetCheckOutbound(c *gin.Context) {
	tag := c.Query("tag")
	link := c.Query("link")
	result := a.ConfigService.CheckOutbound(tag, link)
	jsonObj(c, result, nil)
}
