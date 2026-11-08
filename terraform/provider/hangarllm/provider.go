package hangarllm

import (
	"github.com/hashicorp/terraform-plugin-sdk/v2/helper/schema"
)

// Provider returns a terraform.ResourceProvider.
func Provider() *schema.Provider {
	return &schema.Provider{
		ResourcesMap: map[string]*schema.Resource{
			"hangarllm_model":                   resourceHangarLLMModel(),
			"hangarllm_team":                    ResourceHangarLLMTeam(),
			"hangarllm_organization":            resourceHangarLLMOrganization(),
			"hangarllm_organization_member":     resourceHangarLLMOrganizationMember(),
			"hangarllm_organization_member_add": resourceHangarLLMOrganizationMemberAdd(),
			"hangarllm_team_member":             resourceHangarLLMTeamMember(),
			"hangarllm_team_member_add":         resourceHangarLLMTeamMemberAdd(),
			"hangarllm_key":                     resourceKey(),
			"hangarllm_mcp_server":              resourceHangarLLMMCPServer(),
			"hangarllm_credential":              resourceHangarLLMCredential(),
			"hangarllm_vector_store":            resourceHangarLLMVectorStore(),
			"hangarllm_jwt_key_mapping":         resourceHangarLLMJWTKeyMapping(),
			"hangarllm_fallback":                resourceHangarLLMFallback(),
			"hangarllm_key_block":               resourceHangarLLMKeyBlock(),
			"hangarllm_team_block":              resourceHangarLLMTeamBlock(),
			"hangarllm_access_group":            resourceHangarLLMAccessGroup(),
			"hangarllm_unified_access_group":    resourceHangarLLMUnifiedAccessGroup(),
			"hangarllm_guardrail":               resourceHangarLLMGuardrail(),
			"hangarllm_prompt":                  resourceHangarLLMPrompt(),
			"hangarllm_agent":                   resourceHangarLLMAgent(),
			"hangarllm_search_tool":             resourceHangarLLMSearchTool(),
			"hangarllm_user":                    resourceHangarLLMUser(),
			"hangarllm_budget":                  resourceHangarLLMBudget(),
			"hangarllm_tag":                     resourceHangarLLMTag(),
			"hangarllm_project":                 resourceHangarLLMProject(),
		},
		DataSourcesMap: map[string]*schema.Resource{
			"hangarllm_credential":            dataSourceHangarLLMCredential(),
			"hangarllm_vector_store":          dataSourceHangarLLMVectorStore(),
			"hangarllm_fallback":              dataSourceHangarLLMFallback(),
			"hangarllm_access_group":          dataSourceHangarLLMAccessGroup(),
			"hangarllm_access_groups":         dataSourceHangarLLMAccessGroups(),
			"hangarllm_unified_access_group":  dataSourceHangarLLMUnifiedAccessGroup(),
			"hangarllm_unified_access_groups": dataSourceHangarLLMUnifiedAccessGroups(),
			"hangarllm_guardrail":             dataSourceHangarLLMGuardrail(),
			"hangarllm_guardrails":            dataSourceHangarLLMGuardrails(),
			"hangarllm_prompt":                dataSourceHangarLLMPrompt(),
			"hangarllm_prompts":               dataSourceHangarLLMPrompts(),
			"hangarllm_agent":                 dataSourceHangarLLMAgent(),
			"hangarllm_agents":                dataSourceHangarLLMAgents(),
			"hangarllm_search_tool":           dataSourceHangarLLMSearchTool(),
			"hangarllm_search_tools":          dataSourceHangarLLMSearchTools(),
			"hangarllm_user":                  dataSourceHangarLLMUser(),
			"hangarllm_users":                 dataSourceHangarLLMUsers(),
			"hangarllm_budget":                dataSourceHangarLLMBudget(),
			"hangarllm_budgets":               dataSourceHangarLLMBudgets(),
			"hangarllm_tag":                   dataSourceHangarLLMTag(),
			"hangarllm_tags":                  dataSourceHangarLLMTags(),
			"hangarllm_project":               dataSourceHangarLLMProject(),
			"hangarllm_projects":              dataSourceHangarLLMProjects(),
			"hangarllm_key":                   dataSourceHangarLLMKey(),
			"hangarllm_keys":                  dataSourceHangarLLMKeys(),
			"hangarllm_team":                  dataSourceHangarLLMTeam(),
			"hangarllm_teams":                 dataSourceHangarLLMTeams(),
			"hangarllm_model":                 dataSourceHangarLLMModel(),
			"hangarllm_models":                dataSourceHangarLLMModels(),
			"hangarllm_organization":          dataSourceHangarLLMOrganization(),
			"hangarllm_organizations":         dataSourceHangarLLMOrganizations(),
			"hangarllm_mcp_server":            dataSourceHangarLLMMCPServer(),
			"hangarllm_mcp_servers":           dataSourceHangarLLMMCPServers(),
		},
		Schema: map[string]*schema.Schema{
			"api_base": {
				Type:        schema.TypeString,
				Required:    true,
				Sensitive:   false,
				DefaultFunc: schema.EnvDefaultFunc("HANGARLLM_API_BASE", nil),
				Description: "The base URL of the HangarLLM API",
			},
			"api_key": {
				Type:        schema.TypeString,
				Required:    true,
				Sensitive:   true,
				DefaultFunc: schema.EnvDefaultFunc("HANGARLLM_API_KEY", nil),
				Description: "The API key for authenticating with HangarLLM",
			},
			"insecure_skip_verify": {
				Type:        schema.TypeBool,
				Optional:    true,
				Default:     false,
				DefaultFunc: schema.EnvDefaultFunc("HANGARLLM_INSECURE_SKIP_VERIFY", false),
				Description: "Skip TLS certificate verification. Only use for development or when using self-signed certificates",
			},
		},
		ConfigureFunc: providerConfigure,
	}
}

// providerConfigure configures the provider with the given schema data.
func providerConfigure(d *schema.ResourceData) (interface{}, error) {
	config := ProviderConfig{
		APIBase:            d.Get("api_base").(string),
		APIKey:             d.Get("api_key").(string),
		InsecureSkipVerify: d.Get("insecure_skip_verify").(bool),
	}

	return NewClient(config.APIBase, config.APIKey, config.InsecureSkipVerify), nil
}
