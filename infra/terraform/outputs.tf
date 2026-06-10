output "server_ipv4" {
  description = "Public IPv4 of the Kasia VPS."
  value       = hcloud_server.web.ipv4_address
}

output "server_ipv6" {
  description = "Public IPv6 of the Kasia VPS."
  value       = hcloud_server.web.ipv6_address
}

output "ssh_command" {
  description = "First-login SSH command."
  value       = "ssh root@${hcloud_server.web.ipv4_address}"
}
