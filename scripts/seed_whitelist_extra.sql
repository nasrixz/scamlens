-- Additional safe domains — CDNs and service endpoints major brands use
-- that don't share the primary brand eTLD+1. Apply after seed_whitelist.sql.
--
--   docker compose exec -T postgres \
--     psql -U $POSTGRES_USER -d $POSTGRES_DB < scripts/seed_whitelist_extra.sql

INSERT INTO whitelist (domain, reason) VALUES
  -- WhatsApp / Meta / Instagram CDN
  ('whatsapp.net',          'whatsapp cdn'),
  ('fbcdn.net',             'meta cdn'),
  ('cdninstagram.com',      'instagram cdn'),
  ('fb.com',                'meta short'),
  ('fbsbx.com',             'meta sandbox'),
  ('messenger.com',         'meta messenger'),
  -- Microsoft services / CDN
  ('microsoftonline.com',   'azure ad / m365'),
  ('msftconnecttest.com',   'windows connectivity test'),
  ('msedge.net',            'edge sync'),
  ('msecnd.net',            'azure cdn'),
  ('azureedge.net',         'azure cdn'),
  ('azure.com',             'microsoft azure'),
  ('azure.net',             'microsoft azure'),
  ('windows.com',           'windows services'),
  ('windows.net',           'windows services'),
  ('windowsupdate.com',     'windows update'),
  ('aka.ms',                'microsoft short links'),
  ('office.net',            'office 365'),
  ('office365.com',         'office 365'),
  ('sharepoint.com',        'sharepoint'),
  ('onedrive.com',          'onedrive'),
  ('skype.com',             'skype'),
  ('bing.net',              'bing cdn'),
  ('msn.com',               'msn'),
  ('visualstudio.com',      'vs online'),
  ('xboxlive.com',          'xbox live'),
  ('s-microsoft.com',       'microsoft assets'),
  -- Google CDN + services
  ('ggpht.com',             'google assets'),
  ('youtu.be',              'youtube short'),
  ('googlevideo.com',       'youtube video'),
  ('ytimg.com',             'youtube imagery'),
  ('googletagmanager.com',  'google tag'),
  ('withgoogle.com',        'google projects'),
  -- Apple
  ('apple-cloudkit.com',    'apple icloud backend'),
  ('mzstatic.com',          'apple media cdn'),
  ('itunes.apple.com',      'itunes'),
  ('icloud-content.com',    'icloud'),
  -- Discord / Twitch / Twitter
  ('discordapp.com',        'discord legacy'),
  ('discord.gg',            'discord invites'),
  ('twimg.com',             'twitter images'),
  ('twitch.tv',             'twitch'),
  ('ttvnw.net',             'twitch cdn'),
  -- Amazon / AWS
  ('amazonaws.com',         'aws'),
  ('cloudfront.net',        'aws cdn'),
  ('media-amazon.com',      'amazon assets'),
  ('ssl-images-amazon.com', 'amazon images'),
  -- Cloudflare / CDN / payment
  ('cloudflareinsights.com','cf analytics'),
  ('cloudflare-dns.com',    'cf public dns'),
  ('stripecdn.com',         'stripe cdn'),
  ('paypalobjects.com',     'paypal cdn'),
  -- TikTok
  ('tiktokcdn.com',         'tiktok cdn'),
  ('bytedance.com',         'tiktok parent'),
  ('bytecdn.com',           'tiktok cdn'),
  -- Zoom / Slack / Google Meet
  ('zoomgov.com',           'zoom gov'),
  ('slack-edge.com',        'slack cdn'),
  ('slack-files.com',       'slack files'),
  -- Grab / Shopee / Lazada / Foodpanda
  ('grabtaxi.com',          'grab backend'),
  ('shopeemobile.com',      'shopee mobile'),
  ('lzd-img-global.slatic.net', 'lazada cdn'),
  ('foodpanda.my',          'foodpanda my'),
  -- Malaysian government + banks auxiliaries
  ('myeg.com.my',           'myeg services'),
  ('jpj.gov.my',            'jpj'),
  ('imigresen.gov.my',      'imigresen'),
  ('lhdn.gov.my',           'lhdn'),
  ('pos.com.my',            'pos malaysia'),
  ('maybank2u.com.my',      'maybank online banking'),
  ('cimbclicks.com.my',     'cimb clicks'),
  ('cimbbiz.com.my',        'cimb biz'),
  -- NTP / OCSP (browsers hit these constantly)
  ('pool.ntp.org',          'ntp pool'),
  ('digicert.com',          'ca / ocsp'),
  ('letsencrypt.org',       'ca'),
  ('sectigo.com',           'ca / ocsp'),
  ('entrust.net',           'ca'),
  ('globalsign.com',        'ca'),
  -- Apple push / Google push
  ('push.apple.com',        'apple push'),
  ('gcm.googleapis.com',    'firebase push')
ON CONFLICT (domain) DO NOTHING;
