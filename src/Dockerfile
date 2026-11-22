# The Librarian image: both hosts built in the SDK stage, published into the aspnet runtime.
# The Api is the entrypoint; the Ingest runs from the same image with the entrypoint overridden
# (compose at the deploy: ["dotnet", "ingest/Ingest.dll"]).
# The image carries appsettings.json only: every machine path, port and secret comes from the
# environment, and appsettings.{Environment}.json never enters Git.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY Directory.Build.props Directory.Packages.props nuget.config ./
COPY librarian/Application/Application.csproj librarian/Application/packages.lock.json librarian/Application/
COPY librarian/Adapters/Adapters.csproj librarian/Adapters/packages.lock.json librarian/Adapters/
COPY librarian/Api/Api.csproj librarian/Api/packages.lock.json librarian/Api/
COPY librarian/Ingest/Ingest.csproj librarian/Ingest/packages.lock.json librarian/Ingest/
RUN dotnet restore librarian/Api/Api.csproj --locked-mode \
    && dotnet restore librarian/Ingest/Ingest.csproj --locked-mode

COPY . .
RUN dotnet publish librarian/Api -c Release -o /publish/api --no-restore \
    && dotnet publish librarian/Ingest -c Release -o /publish/ingest --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /publish/api api
COPY --from=build /publish/ingest ingest
ENV DOTNET_ENVIRONMENT=Production
ENTRYPOINT ["dotnet", "api/Api.dll"]
