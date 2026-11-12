# https://<subdomain>.<domain> → http://<name>:<port>, behind tinyauth (which passes Remote-User).
{...}: {
  neoPlugin.modules.mathtutor-swag = {
    config,
    lib,
    plugin,
    ...
  }: let
    name = plugin.name "mathtutor";
    cfg = config.neo.services.${name};
  in {
    config.neo.services.${name}.proxyConf = lib.mkDefault (lib.neo.mkSubdomainProxyConf {
      inherit config cfg;
      upstream = name;
      port = cfg.port;
    });
  };
}
