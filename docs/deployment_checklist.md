# Team-Based Authorization Deployment Checklist

## Pre-Deployment Verification

### Code Quality
- [x] All tests passing (284 backend + 24 frontend tests)
- [x] TypeScript compilation successful
- [x] No linting errors
- [x] Code reviewed and approved

### Database
- [x] Migration scripts created (`alembic/versions/*_add_teams.py`)
- [ ] Migration tested on staging database
- [ ] Rollback procedure documented
- [ ] Database backup created before migration

### Documentation
- [x] API documentation updated (api_contract.md)
- [x] User guide created (team_management.md)
- [x] README updated with team features
- [x] Design document complete (team_based_authorization.md)

## Staging Deployment

### 1. Database Migration
```bash
# Backup database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migration
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt teams"
psql $DATABASE_URL -c "\dt user_team_memberships"
```

### 2. Backend Deployment
```bash
# Pull latest code
git checkout team_authz_implementation
git pull origin team_authz_implementation

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Restart service
systemctl restart gharts-backend
```

### 3. Frontend Deployment
```bash
# Build frontend
cd frontend
npm install
npm run build

# Deploy static files
cp -r dist/* /var/www/gharts/

# Verify deployment
curl https://your-domain.com/app
```

### 4. Smoke Tests
- [ ] Health endpoint responds: `GET /health`
- [ ] Admin can access teams page: `GET /api/v1/admin/teams`
- [ ] Create test team via API
- [ ] Add test user to team
- [ ] Provision runner with team
- [ ] Verify audit logs include team information

## Production Deployment

### Pre-Deployment
- [ ] Staging tests completed successfully
- [ ] Rollback plan reviewed
- [ ] Maintenance window scheduled
- [ ] Stakeholders notified

### Deployment Steps
1. [ ] Enable maintenance mode
2. [ ] Create database backup
3. [ ] Run database migration
4. [ ] Deploy backend code
5. [ ] Deploy frontend code
6. [ ] Run smoke tests
7. [ ] Disable maintenance mode
8. [ ] Monitor logs for errors

### Post-Deployment Verification
- [ ] All existing runners still visible
- [ ] User-based label policies still work
- [ ] New team features accessible to admins
- [ ] No errors in application logs
- [ ] Performance metrics normal

## Migration Strategy

### Phase 1: Soft Launch (Week 1)
- [ ] Deploy team features to production
- [ ] Keep user-based policies as default
- [ ] Create initial teams for pilot users
- [ ] Monitor usage and gather feedback

### Phase 2: Gradual Migration (Weeks 2-4)
- [ ] Migrate teams one by one
- [ ] Train users on new team features
- [ ] Document common issues and solutions
- [ ] Adjust team policies based on feedback

### Phase 3: Full Migration (Week 5+)
- [ ] All users migrated to teams
- [ ] Deprecate user-based label policies
- [ ] Update documentation to reflect team-first approach
- [ ] Remove legacy code (future release)

## Rollback Procedure

### If Issues Detected
1. **Immediate**: Revert to previous deployment
   ```bash
   git checkout main
   systemctl restart gharts-backend
   ```

2. **Database**: Rollback migration if needed
   ```bash
   alembic downgrade -1
   ```

3. **Verify**: Run tests to ensure system stability
   ```bash
   pytest tests/ -v
   ```

### Rollback Triggers
- Critical bugs affecting runner provisioning
- Database performance degradation
- Authentication/authorization failures
- Data corruption or loss

## Monitoring

### Key Metrics
- [ ] API response times (< 200ms p95)
- [ ] Database query performance
- [ ] Error rates (< 0.1%)
- [ ] Team creation/membership operations
- [ ] Runner provisioning success rate

### Alerts
- [ ] Failed database migrations
- [ ] API errors > 1% of requests
- [ ] Slow queries > 1 second
- [ ] Authentication failures

### Logs to Monitor
```bash
# Application logs
tail -f /var/log/gharts/app.log | grep -i "team\|error"

# Database logs
tail -f /var/log/postgresql/postgresql.log | grep -i "teams\|error"

# Nginx logs
tail -f /var/log/nginx/access.log | grep "/api/v1/admin/teams"
```

## Communication Plan

### Before Deployment
- [ ] Email to all users about new features
- [ ] Documentation links shared
- [ ] Training sessions scheduled
- [ ] Support channels prepared

### During Deployment
- [ ] Status page updated
- [ ] Real-time updates via Slack/Teams
- [ ] Support team on standby

### After Deployment
- [ ] Success announcement
- [ ] Known issues documented
- [ ] Feedback collection started
- [ ] Follow-up training scheduled

## Success Criteria

### Technical
- [x] All tests passing
- [ ] Zero critical bugs in first 24 hours
- [ ] API response times within SLA
- [ ] No data loss or corruption

### Business
- [ ] At least 3 teams created in first week
- [ ] 80% of pilot users successfully provision runners
- [ ] Positive feedback from early adopters
- [ ] No escalations to engineering

## Troubleshooting

### Common Issues

**Issue**: Team dropdown not showing
- **Cause**: User not member of any team
- **Solution**: Add user to team or provision without team

**Issue**: "Label not permitted" error
- **Cause**: Label doesn't match team policy
- **Solution**: Update team policy or use different labels

**Issue**: "Team quota exceeded"
- **Cause**: Team reached max_runners limit
- **Solution**: Increase quota or remove idle runners

**Issue**: Migration fails
- **Cause**: Database constraints or conflicts
- **Solution**: Check logs, fix data issues, retry migration

### Support Contacts
- **Engineering**: engineering@example.com
- **DevOps**: devops@example.com
- **On-Call**: +1-555-0123

## Post-Deployment Tasks

### Week 1
- [ ] Daily monitoring of metrics
- [ ] Collect user feedback
- [ ] Document issues and resolutions
- [ ] Update FAQ based on questions

### Week 2-4
- [ ] Weekly review of team usage
- [ ] Adjust policies based on patterns
- [ ] Plan next phase of migration
- [ ] Prepare training materials

### Month 2+
- [ ] Evaluate success metrics
- [ ] Plan deprecation of user-based policies
- [ ] Consider additional features
- [ ] Update roadmap

---

**Deployment Date**: _____________  
**Deployed By**: _____________  
**Approved By**: _____________  
**Rollback Tested**: [ ] Yes [ ] No