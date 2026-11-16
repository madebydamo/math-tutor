# https://<subdomain>.<domain> → http://<name>:<port>, behind tinyauth (which passes Remote-User).
# SWAG also sends X-Neo-Proxy-Secret (generated secret `<name>-proxy`, rendered into a
# SWAG include so it never lands in the store); the app ignores Remote-User without it.
{...}: {
  neoPlugin.modules.mathtutor-swag = {
    config,
    lib,
    plugin,
    ...
  }: let
    name = plugin.name "mathtutor";
    cfg = config.neo.services.${name};
    proxySecret = lib.neo.secrets.swagSnippet config "${name}-proxy" ''
      proxy_set_header X-Neo-Proxy-Secret "${lib.neo.secrets.mkPlaceholder "generated/${name}-proxy"}";
    '';
  in {
    config = {
      neo.services.${name}.proxyConf = lib.mkDefault (lib.neo.mkSubdomainProxyConf {
        inherit config cfg;
        upstream = name;
        port = cfg.port;
        locationExtra = "    ${proxySecret.include}";
      });
      neo.core.secrets.templates = lib.mkIf cfg.enabled proxySecret.templates;
    };
  };
}
